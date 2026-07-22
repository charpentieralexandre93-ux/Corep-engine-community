"""
================================================================================
MODULE  : engine_contracts.py
PROJET  : COREP Engine CRR3
VERSION : 6.10.1
================================================================================

Contrat d'exécution commun des moteurs réglementaires.

La couche est volontairement additive : les fonctions historiques
``run_*_engine(db, batch_id, regulatory_version_id, reporting_date, **kwargs)``
restent inchangées. ``FunctionEngineAdapter`` les expose derrière le protocole
``RegulatoryEngine`` afin de permettre une migration progressive, sans rupture
API ni modification des calculs réglementaires.

Le module fournit également un profiler léger par moteur. Il mesure uniquement
le temps d'exécution autour du contrat normalisé et produit des rapports JSON et
CSV auditables. Il n'altère ni les transactions, ni l'ordre d'exécution, ni les
résultats des moteurs.
================================================================================
"""

from __future__ import annotations

import csv
import json
import logging
import os
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Mapping,
    Optional,
    Protocol,
    Tuple,
    Union,
    runtime_checkable,
)


@dataclass(frozen=True)
class EngineContext:
    """Contexte immuable transmis à tout moteur réglementaire.

    Parameters
    ----------
    db:
        Façade de base de données utilisée par le batch.
    batch_id:
        Identifiant de corrélation et de traçabilité du batch.
    regulatory_version_id:
        Version réglementaire active, par exemple ``CRR3_V9``.
    reporting_date:
        Date d'arrêté telle qu'attendue par les moteurs existants.
    config:
        Configuration complète du run, disponible pour les moteurs migrés vers
        le nouveau contrat. Les adaptateurs legacy ne la transmettent pas
        implicitement afin de préserver leurs signatures historiques.
    runtime_kwargs:
        Arguments spécifiques au moteur, déjà résolus par le registry.
    engine_key / engine_label:
        Métadonnées d'observabilité, sans incidence sur le calcul.
    """

    db: Any
    batch_id: str
    regulatory_version_id: str
    reporting_date: Any
    config: Mapping[str, Any] = field(default_factory=dict)
    runtime_kwargs: Mapping[str, Any] = field(default_factory=dict)
    engine_key: str = ""
    engine_label: str = ""

    def kwargs(self) -> Dict[str, Any]:
        """Retourne une copie mutable des arguments spécifiques au moteur."""
        return dict(self.runtime_kwargs)


@dataclass(frozen=True)
class EngineResult:
    """Résultat normalisé d'un moteur.

    ``processed_rows`` conserve exactement la sémantique des retours ``int``
    historiques. Les champs additionnels permettent d'enrichir progressivement
    les moteurs sans casser le batch existant.
    """

    processed_rows: int
    warnings: Tuple[str, ...] = ()
    metrics: Mapping[str, float] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_legacy(cls, value: Union["EngineResult", int, None]) -> "EngineResult":
        """Normalise un retour historique ``int | None`` en ``EngineResult``."""
        if isinstance(value, cls):
            return value
        return cls(processed_rows=int(value or 0))

    def __int__(self) -> int:
        """Compatibilité pratique avec les compteurs historiques."""
        return self.processed_rows


@runtime_checkable
class RegulatoryEngine(Protocol):
    """Interface structurelle minimale de tout moteur réglementaire."""

    def run(self, context: EngineContext) -> EngineResult:
        """Exécute le moteur dans le contexte fourni."""
        ...


LegacyEngineCallable = Callable[..., Union[EngineResult, int, None]]


class FunctionEngineAdapter:
    """Adapte une fonction moteur historique au protocole ``RegulatoryEngine``."""

    def __init__(self, function: LegacyEngineCallable, *, name: Optional[str] = None) -> None:
        if not callable(function):
            raise TypeError("function doit être callable")
        self._function = function
        self.name = name or getattr(function, "__name__", function.__class__.__name__)

    @property
    def function(self) -> LegacyEngineCallable:
        """Expose le callable legacy pour audit et tests de compatibilité."""
        return self._function

    def run(self, context: EngineContext) -> EngineResult:
        raw_result = self._function(
            context.db,
            context.batch_id,
            context.regulatory_version_id,
            context.reporting_date,
            **context.kwargs(),
        )
        return EngineResult.from_legacy(raw_result)


@dataclass(frozen=True)
class EngineProfile:
    """Mesure d'exécution d'un moteur, sérialisable dans les rapports."""

    engine_key: str
    engine_label: str
    status: str
    started_at_utc: str
    finished_at_utc: str
    duration_seconds: float
    processed_rows: int
    throughput_rows_per_second: Optional[float]
    warning_count: int
    error_type: Optional[str] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "engine_key": self.engine_key,
            "engine_label": self.engine_label,
            "status": self.status,
            "started_at_utc": self.started_at_utc,
            "finished_at_utc": self.finished_at_utc,
            "duration_seconds": self.duration_seconds,
            "processed_rows": self.processed_rows,
            "throughput_rows_per_second": self.throughput_rows_per_second,
            "warning_count": self.warning_count,
            "error_type": self.error_type,
            "error_message": self.error_message,
        }


class EngineProfiler:
    """Profiler séquentiel léger autour du contrat ``RegulatoryEngine``.

    Le profiler ne capture pas les exceptions : il enregistre la mesure en
    échec puis relance l'exception originale, ce qui préserve intégralement la
    sémantique transactionnelle du batch.
    """

    def __init__(
        self,
        logger: Optional[logging.Logger] = None,
        *,
        enabled: bool = True,
        slow_threshold_seconds: float = 5.0,
    ) -> None:
        self._logger = logger or logging.getLogger(__name__)
        self.enabled = bool(enabled)
        self.slow_threshold_seconds = max(float(slow_threshold_seconds), 0.0)
        self._profiles: List[EngineProfile] = []

    @property
    def profiles(self) -> Tuple[EngineProfile, ...]:
        """Snapshot immuable des mesures collectées."""
        return tuple(self._profiles)

    def run(
        self,
        engine: RegulatoryEngine,
        context: EngineContext,
        *,
        engine_key: Optional[str] = None,
        engine_label: Optional[str] = None,
    ) -> EngineResult:
        """Exécute et profile un moteur, sans modifier son contrat métier."""
        if not self.enabled:
            return engine.run(context)

        key = engine_key or context.engine_key or engine.__class__.__name__
        label = engine_label or context.engine_label or key
        started_wall = datetime.now(timezone.utc)
        started_perf = time.perf_counter()

        try:
            result = engine.run(context)
        except Exception as exc:  # fail-closed: error is re-raised or translated after cleanup
            finished_wall = datetime.now(timezone.utc)
            duration = round(time.perf_counter() - started_perf, 6)
            profile = EngineProfile(
                engine_key=key,
                engine_label=label,
                status="FAILED",
                started_at_utc=started_wall.isoformat(),
                finished_at_utc=finished_wall.isoformat(),
                duration_seconds=duration,
                processed_rows=0,
                throughput_rows_per_second=None,
                warning_count=0,
                error_type=type(exc).__name__,
                error_message=str(exc)[:500],
            )
            self._profiles.append(profile)
            self._logger.error(
                "Profil moteur %-16s : FAILED en %.6fs (%s)",
                label,
                duration,
                type(exc).__name__,
                extra={
                    "metric": "engine_duration_seconds",
                    "metric_value": duration,
                    "engine_key": key,
                    "engine_label": label,
                    "engine_status": "FAILED",
                },
            )
            raise

        finished_wall = datetime.now(timezone.utc)
        duration = round(time.perf_counter() - started_perf, 6)
        throughput = (
            round(result.processed_rows / duration, 3) if duration > 0.0 and result.processed_rows > 0 else None
        )
        profile = EngineProfile(
            engine_key=key,
            engine_label=label,
            status="COMPLETED",
            started_at_utc=started_wall.isoformat(),
            finished_at_utc=finished_wall.isoformat(),
            duration_seconds=duration,
            processed_rows=result.processed_rows,
            throughput_rows_per_second=throughput,
            warning_count=len(result.warnings),
        )
        self._profiles.append(profile)

        log_method = self._logger.warning if duration >= self.slow_threshold_seconds > 0.0 else self._logger.info
        log_method(
            "Profil moteur %-16s : %d ligne(s) en %.6fs%s",
            label,
            result.processed_rows,
            duration,
            f" ({throughput:.3f} lignes/s)" if throughput is not None else "",
            extra={
                "metric": "engine_duration_seconds",
                "metric_value": duration,
                "engine_key": key,
                "engine_label": label,
                "engine_status": "COMPLETED",
                "processed_rows": result.processed_rows,
                "throughput_rows_per_second": throughput,
            },
        )
        return result

    def summary(self) -> Dict[str, Any]:
        """Agrégats du profil courant."""
        completed = sum(1 for p in self._profiles if p.status == "COMPLETED")
        failed = sum(1 for p in self._profiles if p.status == "FAILED")
        return {
            "engine_count": len(self._profiles),
            "completed_count": completed,
            "failed_count": failed,
            "total_duration_seconds": round(sum(p.duration_seconds for p in self._profiles), 6),
            "total_processed_rows": sum(p.processed_rows for p in self._profiles),
        }

    def write_reports(self, output_dir: Union[str, Path], batch_id: str) -> Tuple[Path, Path]:
        """Écrit les profils JSON et CSV de façon atomique.

        Retourne ``(json_path, csv_path)``. Si le profiler est désactivé, les
        fichiers sont tout de même cohérents mais contiennent zéro moteur ; le
        batch choisit de ne pas appeler cette méthode dans ce cas.
        """
        directory = Path(output_dir)
        directory.mkdir(parents=True, exist_ok=True)
        safe_batch_id = "".join(
            character if character.isalnum() or character in {"-", "_"} else "_" for character in str(batch_id)
        )
        json_path = directory / f"engine_profile_{safe_batch_id}.json"
        csv_path = directory / f"engine_profile_{safe_batch_id}.csv"

        payload = {
            "schema_version": 1,
            "batch_id": str(batch_id),
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "summary": self.summary(),
            "engines": [profile.to_dict() for profile in self._profiles],
        }
        self._atomic_write_text(
            json_path,
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        )

        headers = [
            "engine_key",
            "engine_label",
            "status",
            "started_at_utc",
            "finished_at_utc",
            "duration_seconds",
            "processed_rows",
            "throughput_rows_per_second",
            "warning_count",
            "error_type",
            "error_message",
        ]
        fd, temporary_name = tempfile.mkstemp(prefix=f".{csv_path.name}.", suffix=".tmp", dir=str(directory))
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=headers)
                writer.writeheader()
                for profile in self._profiles:
                    writer.writerow(profile.to_dict())
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, csv_path)
        except Exception:  # fail-closed: error is re-raised or translated after cleanup
            try:
                os.unlink(temporary_name)
            except OSError:
                pass
            raise

        return json_path, csv_path

    @staticmethod
    def _atomic_write_text(path: Path, content: str) -> None:
        fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, path)
        except Exception:  # fail-closed: error is re-raised or translated after cleanup
            try:
                os.unlink(temporary_name)
            except OSError:
                pass
            raise


__all__ = [
    "EngineContext",
    "EngineResult",
    "RegulatoryEngine",
    "FunctionEngineAdapter",
    "EngineProfile",
    "EngineProfiler",
]

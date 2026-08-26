from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from django.core.management.base import BaseCommand
from django.core.management.base import CommandError

from core.sample_data import clear_seed_spec
from core.sample_data import iter_sample_data_choices
from core.sample_data import load_seed_spec
from core.sample_data import resolve_seed_specs

if TYPE_CHECKING:
    from argparse import ArgumentParser


class Command(BaseCommand):
    help = "Load JSON-backed sample data for one or more models."

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--model",
            action="append",
            default=[],
            help=(
                "Friendly model name to load, e.g. 'currency' or "
                "'product category'. Repeat to load more than one."
            ),
        )
        parser.add_argument(
            "--fresh",
            action="store_true",
            help="Delete the selected model rows before loading the JSON data.",
        )

    def handle(self, *args: str, **options: Any) -> str:
        selected_models = options.get("model") or []
        fresh = bool(options.get("fresh"))

        specs = resolve_seed_specs(selected_models)
        if not specs:
            msg = (
                "No sample data models were selected. "
                f"Available choices: {', '.join(iter_sample_data_choices())}"
            )
            raise CommandError(msg)

        if fresh:
            for spec in reversed(specs):
                self.stdout.write(f"Clearing {spec.label} ...")
                clear_seed_spec(spec)

        for spec in specs:
            self.stdout.write(f"Loading {spec.label} ...")
            load_seed_spec(spec, fresh=False)

        return self.style.SUCCESS("Sample data load complete.")

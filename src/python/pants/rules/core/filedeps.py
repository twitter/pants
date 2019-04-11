# coding=utf-8
# Copyright 2018 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import absolute_import, division, print_function, unicode_literals

from pex.orderedset import OrderedSet

from pants.engine.console import LineOrientedOutput
from pants.engine.legacy.graph import TransitiveHydratedTargets
from pants.engine.rules import console_rule


@console_rule('filedeps', [LineOrientedOutput, TransitiveHydratedTargets])
def file_deps(line_oriented_output, transitive_hydrated_targets):
  """List all source and BUILD files a target transitively depends on.

  Files are listed with relative paths and any BUILD files implied in the transitive closure of
  targets are also included.
  """

  uniq_set = OrderedSet()

  for hydrated_target in transitive_hydrated_targets.closure:
    if hydrated_target.address.rel_path:
      uniq_set.add(hydrated_target.address.rel_path)
    if hasattr(hydrated_target.adaptor, "sources"):
      uniq_set.update(f for f in hydrated_target.adaptor.sources.snapshot.files)

  with line_oriented_output.open() as (print_stdout, _):
    for f_path in uniq_set:
      print_stdout(f_path)


def rules():
  return [
      file_deps,
    ]

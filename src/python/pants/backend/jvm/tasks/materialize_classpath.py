# coding=utf-8
# Copyright 2019 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import absolute_import, division, print_function, unicode_literals

import os

from pants.backend.jvm.tasks.classpath_products import ClasspathProducts
from pants.backend.jvm.tasks.classpath_util import ClasspathUtil
from pants.java.util import safe_classpath
from pants.task.task import Task


class _ClasspathEntriesDigestFingerprintStrategy(FingerprintStrategy):
  """Uses the Digests of ClasspathEntries to decide the fingerprint for a target."""

  def __init__(self, unmaterialized_runtime_classpath):
    self._unmaterialized_runtime_classpath = unmaterialized_runtime_classpath

  def compute_fingerprint(self, target):
    entries = 
    hasher = hashlib.sha1()
    for entry in self._unmaterialized_runtime_classpath.get_classpath_entries_for_targets([target]):
      dd = entry.directory_digest
      if dd is not None:
        hasher.update(dd.fingerprint.encode('utf-8'))
      else:
        hasher.update(b'<none>')
    return hasher.hexdigest() if PY3 else hasher.hexdigest().decode('utf-8')


class MaterializeClasspath(Task):
  """Materializes (checks out from the local or remote CAS store) the runtime classpath."""

  @classmethod
  def product_types(cls):
    return ['runtime_classpath']

  @classmethod
  def prepare(cls, options, round_manager):
    round_manager.require_data('unmaterialized_runtime_classpath')

  @property
  def create_target_dirs(self):
    return True

  def _compute_output_entries(self, target, classpath_products):
    """Computes materialized entries for the given target in cases where entries have digests.
    
    The output entries will be located relative to this task's target directories.
    """
    result = []
    for idx, input_entry in enumerate(unmaterialized_product.get_for_target(vt.target)):
      if input_entry.directory_digest is None:
        result.append(input_entry)
        continue

      # Clone the entry with a new path.
      output_entry = input_entry.copy()
      output_entry.path = ...
      # TODO: Relativizing this will be interesting for jars. But could maybe just make up a new name.

  def execute(self):
    unmaterialized_product = self.context.products.get_data('unmaterialized_runtime_classpath')
    materialized_product = self.context.products.get_data('runtime_classpath')
    with self.invalidated(self.context.targets(),
                          invalidate_dependents=True,
                          fingerprint_strategy=fingerprint_strategy) as invalidation_check:
      # Relativize the classpath entry to our output directory, and then materialize it there
      # if need be.
      for vt in invalidation_check.all_vts:
        entry_mapping = self._compute_entry_mapping(target, unmaterialized_product)
        if not vt.valid:
          self._materialize(target, entry_mapping)
        self._publish(target, entry_mapping)

# coding=utf-8
# Copyright 2016 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import absolute_import, division, print_function, unicode_literals

from pex.interpreter import PythonInterpreter

from pants.backend.python.subsystems.pex_build_util import has_python_requirements, is_python_target
from pants.backend.python.tasks.resolve_requirements_task_base import ResolveRequirementsTaskBase


class ResolveRequirements(ResolveRequirementsTaskBase):
  """Resolve external Python requirements."""
  REQUIREMENTS_PEX = 'python_requirements_pex'
  PREPEND_REQUIREMENTS_PEX = 'prepended_requirements_pex'

  options_scope = 'resolve-requirements'

  @classmethod
  def product_types(cls):
    return [
      cls.REQUIREMENTS_PEX,
      cls.PREPEND_REQUIREMENTS_PEX,
    ]

  @classmethod
  def prepare(cls, options, round_manager):
    round_manager.require_data(PythonInterpreter)

  def execute(self):
    if not self.context.targets(lambda t: is_python_target(t) or has_python_requirements(t)):
      return
    interpreter = self.context.products.get_data(PythonInterpreter)

    pre_requirement_targets = []
    post_requirement_targets = []
    for tgt in self.get_targets(has_python_requirements):
      if tgt.prepend_to_pythonpath:
        pre_requirement_targets.append(tgt)
      else:
        post_requirement_targets.append(tgt)

    post_pex = self.resolve_requirements(interpreter, post_requirement_targets)
    self.context.products.register_data(self.REQUIREMENTS_PEX, post_pex)

    if pre_requirement_targets:
      self.context.log.debug('pre_requirement_targets: {}'.format(pre_requirement_targets))
      pre_pex = self.resolve_requirements(interpreter, pre_requirement_targets)
      self.context.products.register_data(self.PREPEND_REQUIREMENTS_PEX, pre_pex)

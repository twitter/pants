# coding=utf-8
# Copyright 2018 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import absolute_import, division, print_function, unicode_literals

from contextlib import contextmanager

from pants.engine.rules import RootRule, optionable_rule, rule
from pants.subsystem.subsystem import Subsystem
from pants.util.objects import datatype


class LineOriented(Subsystem):
  options_scope = 'lines'

  @classmethod
  def register_options(cls, register):
    super(LineOriented, cls).register_options(register)
    register('--sep', default='\\n', metavar='<separator>',
             help='String to use to separate result lines.')
    register('--output-file', metavar='<path>',
             help='Write line-oriented output to this file instead.')

  def output_file(self):
    return self.get_options().output_file

  def sep(self):
    return self.get_options().sep.encode('utf-8').decode('unicode_escape')


class _RawConsole(datatype(['stdout', 'stderr'])):
  """An un-improved Console. Not for direct usage.

  A @console_rule may request either a Console or LineOrientedConsole, depending on whether it
  produces structured output.
  """

  def flush(self):
    self.stdout.flush()
    self.stderr.flush()


class Console(datatype([
  ('raw_console', _RawConsole),
])):
  """A Console for unstructured output."""

  def write_stdout(self, payload):
    self.raw_console.stdout.write(payload)

  def write_stderr(self, payload):
    self.raw_console.stderr.write(payload)

  def print_stdout(self, payload):
    print(payload, file=self.raw_console.stdout)

  def print_stderr(self, payload):
    print(payload, file=self.raw_console.stderr)

  def flush(self):
    self.raw_console.flush()


class LineOrientedOutput(datatype([
  ('raw_console', _RawConsole),
  ('lines', LineOriented),
])):
  """A Console that has been configured for structured (by lines) output, possibly to a file."""

  @contextmanager
  def open(self):
    """A contextmanager that yields functions for writing to stdout and to stderr, respectively."""

    output_file = self.lines.output_file()
    sep = self.lines.sep()

    stdout, stderr = self.raw_console.stdout, self.raw_console.stderr
    if output_file:
      stdout = open(self.lines.get_options().output_file, 'w')

    try:
      print_stdout = lambda msg: print(msg, file=stdout, end=sep)
      print_stderr = lambda msg: print(msg, file=stderr)
      yield print_stdout, print_stderr
    finally:
      if output_file:
        stdout.close()
      else:
        stdout.flush()
      stderr.flush()


@rule(Console, [_RawConsole])
def console(raw_console):
  return Console(raw_console)


@rule(LineOrientedOutput, [_RawConsole, LineOriented])
def line_oriented_output(raw_console, lines):
  return LineOrientedOutput(raw_console, lines)


def rules():
  return [
      RootRule(_RawConsole),
      console,
      line_oriented_output,
      optionable_rule(LineOriented),
    ]

import difflib
import itertools
import os
import signal
from string import Template
import subprocess
import sys
import time
import tempfile

import utils
from utils import GradingException
import common

MAX_LINE_EDIT_DISTANCE = 200

# Splits a source code string into lines, removing empty lines
def get_clean_lines(code):
  return [line for line in code.strip().split("\n") if line.strip()]

# Checks if two lines are the same, ignoring trailing whitespace
def has_line_changed(our_line, their_line, extension):
  if extension == "py":
    return our_line.rstrip() != their_line.rstrip()
  else:
    return our_line.strip() != their_line.strip()

def levenshtein(s1, s2):
  # Source: http://en.wikibooks.org/wiki/Algorithm_Implementation/Strings/Levenshtein_distance#Python
  
  if len(s1) < len(s2):
    return levenshtein(s2, s1)
 
  # len(s1) >= len(s2)
  if len(s2) == 0:
    return len(s1)
 
  previous_row = xrange(len(s2) + 1)
  for i, c1 in enumerate(s1):
    current_row = [i + 1]
    for j, c2 in enumerate(s2):
      insertions = previous_row[j + 1] + 1 # j+1 instead of j since previous_row and current_row are one character longer
      deletions = current_row[j] + 1       # than s2
      substitutions = previous_row[j] + (c1 != c2)
      current_row.append(min(insertions, deletions, substitutions))
    previous_row = current_row
 
  return previous_row[-1]

def check_line_change(our_line, their_line, extension):
  print 'line to check: "%s" -> "%s"' % (our_line, their_line) # DEBUG
  editDist = levenshtein(our_line, their_line)
  if editDist > MAX_LINE_EDIT_DISTANCE:
    print editDist # DEBUG
    raise GradingException('Changed more than %d characters' % MAX_LINE_EDIT_DISTANCE)
  

# Check that exactly one line in the file has changed
def check_changes(our_code, their_code, team_extension):
  our_lines = get_clean_lines(our_code)
  their_lines = get_clean_lines(their_code)
  num_lines_added = len(their_lines) - len(our_lines)
  if num_lines_added > 1:
    raise GradingException('Inserted more than one line')
  if num_lines_added < -1:
    raise GradingException('Removed more than one line')
  if num_lines_added != 0:
    if len(our_lines) < len(their_lines):
      shorter_lines, longer_lines = our_lines, their_lines
    else:
      shorter_lines, longer_lines = their_lines, our_lines

    # Find the first line that differs
    for i in xrange(len(shorter_lines)):
      if has_line_changed(shorter_lines[i], longer_lines[i], team_extension):
        diffLine = i
        break
    else:
      diffLine = len(shorter_lines)

    # Check that no other lines differ
    for i in xrange(diffLine, len(shorter_lines)):
      if has_line_changed(shorter_lines[i], longer_lines[i + 1], team_extension):
        raise GradingException('Changed more than one line')

    if len(our_lines) < len(their_lines):
      # Check that insertion is OK
      check_line_change('', longer_lines[diffLine], team_extension)
  else: # num_lines_added == 0
    lines_changed = [
      (our_line, their_line)
      for our_line, their_line
      in itertools.izip(our_lines, their_lines)
      if has_line_changed(our_line, their_line, team_extension)]
    if len(lines_changed) > 1:
      raise GradingException('%d lines changed (only 1 allowed)' % len(lines_changed))
    if len(lines_changed) == 1:
      our_line, their_line = lines_changed[0]
      check_line_change(our_line, their_line, team_extension)

def _run_tests(task, team_filebase, team_extension, team_filename, metadata, verbose):
  '''Execute judge test cases.'''

  time_limit = utils.languages[team_extension]['executer_time_limit'] * task['problem_metadata']['time_multiplier'] 
  num_test_cases = len(task['problem_metadata']['judge_io'])
  
  check_changes(task['problem_metadata']['judge_bugs'][team_extension], task['payload'], team_extension)

  for index, test_case in enumerate(task['problem_metadata']['judge_io']):
    executer_cmd = utils.languages[team_extension]['executer'].substitute(src_filebase=team_filebase, src_filename=team_filename).split()
    
    stdin = tempfile.TemporaryFile(bufsize=52428800)
    stdin.write(test_case['input'])
    stdin.flush()
    stdin.seek(0)

    stdout = tempfile.TemporaryFile(bufsize=52428800)
    
    if verbose:
      stderr = tempfile.TemporaryFile(bufsize=52428800)
    else:
      stderr = open(os.devnull, 'w')
    
    executer = subprocess.Popen(executer_cmd, stdin=stdin, stdout=stdout, stderr=stderr, preexec_fn=os.setsid, close_fds=True)
    start_time = time.time()
    while executer.poll() is None and (time.time() - start_time <= time_limit):
      time.sleep(0.5)
    if executer.poll() is None:
      if verbose:
        utils.progress('Team executable did not finish; killing PID %d after %d seconds' % (executer.pid, time.time() - start_time))
      os.killpg(executer.pid, signal.SIGKILL)
      raise GradingException('Time limit exceeded')
    if executer.returncode != 0:
      if verbose:
        utils.progress('Team executable gave non-zero return code: %d' % executer.returncode)
        stderr.seek(0)
        print stderr.read()
      raise GradingException('Run time error')
    
    stdout.seek(0)
    team_output = stdout.read()
   
    team_output_lines = map(lambda line: line.strip(), team_output.splitlines())
    judge_output_lines = map(lambda line: line.strip(), test_case['output'].splitlines())
    if team_output_lines != judge_output_lines:
      if verbose:
        utils.progress('Failed %2d / %2d' % (index + 1, num_test_cases))
        diff = difflib.Differ()
        sys.stdout.writelines(list(diff.compare(map(lambda line: line + '\n', team_output_lines), map(lambda line: line + '\n', judge_output_lines))))
      raise GradingException('Incorrect output')
    utils.progress('Passed %2d / %2d' % (index + 1, num_test_cases))
  utils.progress('Correct')
  return True

def grade(q, task, verbose):
  '''Grades a bugfix submission.'''

  return common.grade(q, task, verbose, _run_tests)

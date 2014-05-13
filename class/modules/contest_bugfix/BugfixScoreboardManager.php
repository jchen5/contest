<?php
require_once(__DIR__ . DIRECTORY_SEPARATOR . '..' . DIRECTORY_SEPARATOR . '..' . DIRECTORY_SEPARATOR . 'common.php');

class BugfixScoreboardManager {
  public function generateScoreboard($contest_id, $division_id) {
    global $g_curr_contest;
    global $k_judgment_none;
    global $k_judgment_correct;
    global $k_judgment_incorrect;
    try {
      DBManager::begin();
      $info = DBManager::getContestDivisionJudgments($contest_id, $division_id);
      
      $problems = array();
      $scoreboard = array();
      
      $problem_map = array();
      $empty_judgments = array();
      foreach ($info['problems'] as $problem) {
        if ($problem['problem_type'] != 'bugfix') {
          continue;
        }
        $division_metadata = json_decode($problem['division_metadata'], true);
        $problem_map[$problem['problem_id']] = array('index' => count($problems), 'point_value' => $division_metadata['points']);
        array_push($problems, array('problem_id' => intval($problem['problem_id']), 'alias' => $problem['alias']));
        array_push($empty_judgments, $k_judgment_none);
      }
    
      $team_map = array();
      foreach ($info['teams'] as $team) {
        $team_map[$team['team_id']] = count($scoreboard);
        array_push($scoreboard, array('team_id' => intval($team['team_id']), 'username' => $team['username'], 'alias' => $team['alias'], 'score' => 0, 'time' => 0, 'judgments' => $empty_judgments));
      }      
      foreach ($info['judgments'] as $judgment) {
        $problem_id = $judgment['problem_id'];
        $problem_index = $problem_map[$problem_id]['index'];
        $team_index = $team_map[$judgment['team_id']];
        if ($scoreboard[$team_index]['judgments'][$problem_index] < $judgment['judgment']) {
          if ($judgment['judgment'] == $k_judgment_correct) {
            $point_value = $problem_map[$problem_id]['point_value'];
            $scoreboard[$team_index]['score'] += $point_value;
            if ($judgment['time_submitted'] > $scoreboard[$team_index]['time']) {
              $scoreboard[$team_index]['time'] = intval($judgment['time_submitted']);
            }
          }
          $scoreboard[$team_index]['judgments'][$problem_index] = intval($judgment['judgment']);
        }
      }
      
      usort($scoreboard, function ($a, $b) {
        if ($a['score'] == $b['score']) {
          if ($a['time'] == $b['time']) {
            return strcmp($a['alias'], $b['time']);
          }
          if ($a['time'] == 0) {
            return 1;
          }
          if ($b['time'] == 0) {
            return -1;
          }
          return $a['time'] > $b['time'] ? 1 : -1;
        }
        return $a['score'] > $b['score'] ? -1 : 1;
      });
      
      $contest_metadata = json_decode($g_curr_contest['metadata'], true);
      $metadata = array('judge_scoreboard' => $scoreboard, 'problems' => $problems);
      $team_scoreboard = array();
      if (!isset($contest_metadata['time_freeze']) || ($g_curr_contest['time_start'] + $contest_metadata['time_freeze'] > time())) {
        foreach ($scoreboard as $team) {
          array_push($team_scoreboard, array('team_id' => $team['team_id'], 'username' => $team['username'], 'alias' => $team['alias'], 'score' => $team['score'], 'judgments' => $team['judgments']));
        }
        $metadata['team_scoreboard'] = $team_scoreboard;
      }
      else {
        $old_metadata = json_decode(DBManager::getContestDivisionMetadata($contest_id, $division_id), true);
        $metadata['team_scoreboard'] = $old_metadata['team_scoreboard'];
      }
      DBManager::modifyContestDivisionMetadata($contest_id, $division_id, json_encode($metadata));
      DBManager::commit();
      return array('teams' => $team_scoreboard, 'problems' => $problems);
    }
    catch (Exception $e) {
      DBManager::rollback();
      throw $e;
    }
    return false;
  }
  
  public function setIncorrect($contest_id, $division_id, $team_id, $problem_id) {
    global $k_judgment_correct;
    global $k_judgment_incorrect;
    try {
      DBManager::begin();
      $metadata = json_decode(DBManager::getContestDivisionMetadata($contest_id, $division_id), true);
      for ($problem_index = 0; $problem_index < count($metadata['problems']); $problem_index++) {
        if ($metadata['problems'][$problem_index]['problem_id'] == $problem_id) {
          break;
        }
      }
      if ($problem_index >= count($metadata['problems'])) {
        throw new Exception('Problem not found');
      }
      if (!isset($metadata['team_scoreboard'])) {
        throw new Exception('Scoreboard not found');
      }
      for ($team_index = 0; $team_index < count($metadata['team_scoreboard']); $team_index++) {
        if ($metadata['team_scoreboard'][$team_index]['team_id'] == $team_id && $metadata['team_scoreboard'][$team_index]['judgments'][$problem_index] != $k_judgment_correct) {
          $metadata['team_scoreboard'][$team_index]['judgments'][$problem_index] = $k_judgment_incorrect;
        }
      }
      
      for ($team_index = 0; $team_index < count($metadata['judge_scoreboard']); $team_index++) {
        if ($metadata['judge_scoreboard'][$team_index]['team_id'] == $team_id && $metadata['team_scoreboard'][$team_index]['judgments'][$problem_index] != $k_judgment_correct) {
          $metadata['judge_scoreboard'][$team_index]['judgments'][$problem_index] = $k_judgment_incorrect;
        }
      }
      
      $metadata = json_encode($metadata);
      if (DBManager::modifyContestDivisionMetadata($contest_id, $division_id, $metadata) != 1) {
        throw new Exception('Metadata not modified');
      }
      DBManager::commit();
    }
    catch (Exception $e) {
      DBManager::rollback();
      throw $e;
    }
  }
}
?>
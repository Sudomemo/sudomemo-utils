<?php

/*
PPM parser for Sudomemo
github.com/Sudomemo | www.sudomemo.net

Written by James Daniel
github.com/jaames | rakujira.jp

Format documentation can be found on PBSDS' hatena-server wiki:
https://github.com/pbsds/hatena-server/wiki/PPM-format
*/

class ppmParser {
  var $file;
  var $meta = false;
  var $soundMeta = false;
  var $header = false;
  function open($path){
    if (!file_exists($path)) {
      error_log("Error parsing PPM: could not open $path");
      exit();
    }
    $this->file = fopen($path, 'r');
    $this->header = $this->parseHeader();
    // maybe do some other PPM validity checks here
    if($this->header["magic"] !== "PARA"){
      error_log("Error parsing PPM: $path is not a valid PPM");
      exit();
    }
  }
  function close(){
    fclose($this->file);
    $this->header = false;
    $this->meta = false;
    $this->soundMeta = false;
  }
  // As far as I understand, this should automatically close the file when we're done
  function __destruct() {
    $this->close();
  }
  // PARSING FUNCTIONS
  function _getFormatString($spec){
    $formatString = [];
    foreach ($spec as $var => $format) {
      array_push($formatString, $format . $var);
    }
    return join("/", $formatString);
  }
  function parseHeader(){
    $spec = [
      "magic" => "a4",
      "frameDataLength" => "V",
      "soundDataLength" => "V",
      "frameCount" => "v"
    ];
    // seek to start
    fseek($this->file, 0);
    // unpack the header section
    $ret = unpack($this->_getFormatString($spec), fread($this->file, 14));
    // calculate sound data offset
    $ret["soundHeaderOffset"] = 0x06A0 + $ret["frameDataLength"] + $ret["frameCount"] + (4 - ($ret["frameCount"] % 4));
    return $ret;
  }
  function parseMeta(){
    $spec = [
      "lock" => "v",
      "thumbIndex" => "v",
      "rootAuthorName" => "a22",
      "parentAuthorName" => "a22",
      "currentAuthorName" => "a22",
      "parentAuthorID" => "h16",
      "currentAuthorID" => "h16",
      "parentFilename" => "a18",
      "currentFilename" => "a18",
      "rootAuthorID" => "h16",
      "null" => "x8",
      "timestamp" => "V"
    ];
    // unpack meta section
    fseek($this->file, 16);
    $ret = unpack($this->_getFormatString($spec), fread($this->file, 144));
    // unpack the loop flag
    fseek($this->file, 1702);
    $flags = unpack("v", fread($this->file, 2))[1];
    $ret["loop"] = $flags >> 1 & 0x01;
    return $ret;
  }
  function parseSoundHeader(){
    $spec = [
      "BGMLength" => "V",
      "SE1Length" => "V",
      "SE2Length" => "V",
      "SE3Length" => "V",
      "frameSpeed" => "c",
      "BGMSpeed" => "c",
    ];
    // unpack
    fseek($this->file, $this->header["soundHeaderOffset"]);
    $ret = unpack($this->_getFormatString($spec), fread($this->file, 18));
    // get the sound track usage
    $ret["trackUsage"] = [
      "BGM" => ($ret["BGMLength"] > 0) ? 1 : 0,
      "SE1" => ($ret["SE1Length"] > 0) ? 1 : 0,
      "SE2" => ($ret["SE2Length"] > 0) ? 1 : 0,
      "SE3" => ($ret["SE3Length"] > 0) ? 1 : 0
    ];
    // get the offsets for each track
    // the sound data header is 32 bytes long, so skip that
    $offset = 32;
    $ret["BGMOffset"] = $offset;
    $ret["SE1Offset"] = $offset += $ret["BGMLength"];
    $ret["SE2Offset"] = $offset += $ret["SE1Length"];
    $ret["SE3Offset"] = $offset += $ret["SE2Length"];
    return $ret;
  }
  // PRETTY-PRINTING UTILS
  function _prettyFilename($filename){
    $f = unpack("H6MAC/a13random/vedits", $filename);
    return sprintf("%6s_%13s_%03d", strtoupper($f["MAC"]), $f["random"], $f["edits"]);
  }
  function _prettyUsername($username){
    return trim(mb_convert_encoding($username, "UTF-8", "UTF-16LE"), "\0");
  }
  function _prettyFSID($ID){
    return strrev(strtoupper($ID));
  }
  // GETTERS
  // nicely format all ppm metadata
  function getMeta(){
    if (!$this->meta){
      $this->meta = $this->parseMeta();
    }
    if (!$this->soundMeta){
      $this->soundMeta = $this->parseSoundHeader();
    }
    return [
      "lock"           => $this->meta["lock"],
      "loop"           => $this->meta["loop"],
      "frame_count"    => $this->header["frameCount"],
      "frame_speed"    => (8 - $this->soundMeta["frameSpeed"]),
      "thumb_index"    => $this->meta["thumbIndex"],
      "timestamp"      => $this->meta["timestamp"],
      "unix_timestamp" => $this->meta["timestamp"] + 946684800,
      "root" => [
        "author_name" => $this->_prettyUsername($this->meta["rootAuthorName"]),
        "author_ID"   => $this->_prettyFSID($this->meta["rootAuthorID"])
      ],
      "parent" => [
        "author_name" => $this->_prettyUsername($this->meta["parentAuthorName"]),
        "author_ID"   => $this->_prettyFSID($this->meta["parentAuthorID"]),
        "filename"    => $this->_prettyFilename($this->meta["parentFilename"])
      ],
      "current" => [
        "author_name" => $this->_prettyUsername($this->meta["currentAuthorName"]),
        "author_ID"   => $this->_prettyFSID($this->meta["currentAuthorID"]),
        "filename"    => $this->_prettyFilename($this->meta["currentFilename"])
      ],
      "track_usage" => $this->soundMeta["trackUsage"],
      "track_frame_speed" => (8 - $this->soundMeta["BGMSpeed"])
    ];
  }
  // get the TMB
  function getTMB(){
    fseek($this->file, 0);
    return fread($this->file, 1696);
  }
  // get raw sound track data
  function getTrack($track){
    if (!$this->soundMeta){
      $this->soundMeta = $this->parseSoundHeader($this->file);
    }
    if ($this->soundMeta["{$track}Length"] === 0){
      return NULL;
    }
    else {
      fseek($this->file, $this->header["soundHeaderOffset"] + $this->soundMeta["{$track}Offset"]);
      return fread($this->file, $this->soundMeta["{$track}Length"]);
    }
  }
  // check if a PPM is corrupted / incomplete
  function isCorrupted(){
    // calculate what the file length should be, according to the values from the header
    // sound header offset + sound header length + sound data length + signature length
    $targetLength = $this->header["soundHeaderOffset"] + 32 + $this->header["soundDataLength"] + 144;
    // get the "real" byte length of the file buffer
    // then compare it with the calculated target size
    return fstat($this->file)["size"] == $targetLength ? 0 : 1;
  }
}

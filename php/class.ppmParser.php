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
  var $file = false;
  var $meta = false;
  var $soundMeta = false;
  var $header = false;

  function open($path){
    if($this->file) {
      $this->close();
    }

    $testHandle = fopen($path,  "rb");

    if(!$testHandle) {
      error_log("Error parsing PPM: could not open $path");
			return false;
    }

    $wrapperType = stream_get_meta_data($testHandle)["wrapper_type"];

    if ($wrapperType != "plainfile") {
      $this->file = tmpfile();
      fwrite($this->file,file_get_contents($path));
      fclose($testHandle);
    } else {
      $this->file = $testHandle;
    }

    if (!$this->file) {
	    return false; // file open failed
    }

    $this->header = $this->parseHeader();
    // maybe do some other PPM validity checks here
    if($this->header["magic"] !== "PARA"){
      error_log("Error parsing PPM: $path is not a valid PPM");
	    return false;
    }
    return true; // Success!
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
    // unpack
    fseek($this->file, 0);
    // unpack the header section
    $ret = unpack($this->_getFormatString($spec), fread($this->file, 14));
    // off by one fix;
    $ret["frameCount"]++;
    // calculate sound data offset
    $soundDataOffset = 0x06A0 + $ret["frameDataLength"] + $ret["frameCount"];
    // zipalign to next 4 bytes
    if ($soundDataOffset % 4 !== 0) {
      $soundDataOffset += 4 - ($soundDataOffset % 4);
    }
    $ret["soundDataOffset"] = $soundDataOffset;
    return $ret;
  }

  function parseMeta(){
    $spec = [
      "lock" => "v",
      "thumbIndex" => "v",
      "rootAuthorName" => "a22",
      "parentAuthorName" => "a22",
      "currentAuthorName" => "a22",
      "parentAuthorID" => "P",
      "currentAuthorID" => "P",
      "parentFilename" => "a18",
      "currentFilename" => "a18",
      "rootAuthorID" => "P",
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
    fseek($this->file, $this->header["soundDataOffset"]);
    $ret = unpack($this->_getFormatString($spec), fread($this->file, 18));
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
    return strtoupper(sprintf("%6s_%13s_%03d", $f["MAC"], $f["random"], $f["edits"]));
  }

  function _prettyUsername($username){
    return trim(mb_convert_encoding($username, "UTF-8", "UTF-16LE"), "\0");
  }

  function _prettyFSID($ID){
    return sprintf("%016X", $ID);
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
    $formattedMeta = [
      "lock"           => $this->meta["lock"],
      "loop"           => $this->meta["loop"],
      "frame_count"    => $this->header["frameCount"],
      "frame_speed"    => (8 - $this->soundMeta["frameSpeed"]),
      "thumb_index"    => $this->meta["thumbIndex"],
      "timestamp"      => $this->meta["timestamp"],
      "unix_timestamp" => $this->meta["timestamp"] + 946684800,
      "root" => [
        "username" => $this->_prettyUsername($this->meta["rootAuthorName"]),
        "fsid"   => $this->_prettyFSID($this->meta["rootAuthorID"])
      ],
      "parent" => [
        "username" => $this->_prettyUsername($this->meta["parentAuthorName"]),
        "fsid"   => $this->_prettyFSID($this->meta["parentAuthorID"]),
        "filename"    => $this->_prettyFilename($this->meta["parentFilename"])
      ],
      "current" => [
        "username" => $this->_prettyUsername($this->meta["currentAuthorName"]),
        "fsid"   => $this->_prettyFSID($this->meta["currentAuthorID"]),
        "filename"    => $this->_prettyFilename($this->meta["currentFilename"])
      ],
      "track_usage" => [
        "BGM" => $this->soundMeta["BGMLength"] > 0,
        "SE1" => $this->soundMeta["SE1Length"] > 0,
        "SE2" => $this->soundMeta["SE2Length"] > 0,
        "SE3" => $this->soundMeta["SE3Length"] > 0
      ],
      "track_frame_speed" => (8 - $this->soundMeta["BGMSpeed"])
    ];

    $validFSIDs = array_filter(array(
      $formattedMeta["root"]["fsid"],
      $formattedMeta["parent"]["fsid"],
      $formattedMeta["current"]["fsid"]
    ), function ($ID){
      return preg_match("/^[0159][0-9A-F]{6}0[0-9A-F]{8}$/", $ID);
    });

    $validFilenames = array_filter(array(
      $formattedMeta["parent"]["filename"],
      $formattedMeta["current"]["filename"]
    ), function ($filename){
      return preg_match("/^[A-F0-9]{6}_[A-F0-9]{13}_[0-9]{3}$/", $filename);
    });

    if((count($validFSIDs) < 3) || (count($validFilenames) < 2)) {
      return false;
    }

    return $formattedMeta;
  }

  // test to see if a comment PPM is blank
  function isBlankComment(){
    return $this->header["frameDataLength"] === 112;
  }

  // test to check that the frame offset table is valid
  function isFrameTableValid(){
    fseek($this->file, 0x06A0);
    $offsetTableLength = unpack("v", fread($this->file, 2))[1];
    $offsetCount = $offsetTableLength / 4;

    // do some sanity checks on the offset table length itself
    if ($offsetCount > 999 || $offsetCount < 0) {
      return false;
    }
    if ($offsetCount !== $this->header["frameCount"]) {
      return false;
    }

    // unpack the offset table
    fseek($this->file, 6, SEEK_CUR);
    $offsetTable = unpack("V*", fread($this->file, $offsetTableLength));

    // ensure that all frame offsets land within the frame data
    $frameOffsetLimit = $this->header["frameDataLength"] - $offsetTableLength - 8;
    foreach ($offsetTable as $frameOffset) {
      if ($frameOffset > $frameOffsetLimit || $frameOffset < 0) {
        return false;
      }
    }

    // if it passed all that then, we're good
    return true;
  }

  // get the TMB
  function getTMB(){
    fseek($this->file, 0);
    return fread($this->file, 1696);
  }

  // get raw sound track data
  function getTrack($track){
    if (!$this->soundMeta){
      $this->soundMeta = $this->parseSoundHeader();
    }
    if ($this->soundMeta["{$track}Length"] === 0){
      return NULL;
    }
    else {
      fseek($this->file, $this->header["soundDataOffset"] + $this->soundMeta["{$track}Offset"]);
      return fread($this->file, $this->soundMeta["{$track}Length"]);
    }
  }

  // get a md5sum of the BGM track data
  function getBGMDigest(){
    if (!$this->soundMeta){
      $this->soundMeta = $this->parseSoundHeader();
    }
    if ($this->soundMeta["BGMLength"] === 0){
      return NULL;
    }
    else {
      return md5($this->getTrack("BGM"));
    }
  }
}

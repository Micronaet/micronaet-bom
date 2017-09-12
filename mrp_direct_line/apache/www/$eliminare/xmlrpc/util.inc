<?php
$user       = 'admin';
$password    = 'cgp.fmsp6';
$dbname    = 'Fiam2017S';
$server_url = 'http://192.168.100.166:18069/xmlrpc/';
$userId    = -1;

class OpenErpConnection
{
        public $user;
        public $userId;
        public $password;
        public $database;
        public $url;
        public $connection;
        public $cached;

        function __construct($user, $password, $database, $url){
                $this->user = $user;
                $this->password = $password;
                $this->database = $database;
                $this->url = $url;
        }

        function login(){
                $msg = new xmlrpcmsg('login');
                $msg->addParam(new xmlrpcval($this->database, "string"));
                $msg->addParam(new xmlrpcval($this->user   , "string"));
                $msg->addParam(new xmlrpcval($this->password, "string"));
            $val = $this->_cache_request($this->url.'common',$msg);
            
                $this->userId = $val->scalarVal();

            if($this->userId > 0) {
               return $this->userId;
            }else{
               echo '<br><br><br><h2 align=center>Connection failure....</h2>';
               die();
            }
        }

        function search($relation,$domain){
                $msg = new xmlrpcmsg('execute');
                $msg->addParam(new xmlrpcval($this->database, "string"));
                $msg->addParam(new xmlrpcval($this->userId   , "int"));
                $msg->addParam(new xmlrpcval($this->password, "string"));
                $msg->addParam(new xmlrpcval($relation      , "string"));
                $msg->addParam(new xmlrpcval("search"      , "string"));
                $msg->addParam(php_xmlrpc_encode($domain));
            $val = $this->_cache_request($this->url.'object',$msg);
            
                return php_xmlrpc_decode($val);
        }

        function read($relation,$ids,$fields=array(),$context=array()){
                $msg = new xmlrpcmsg('execute');
                $msg->addParam(new xmlrpcval($this->database, "string"));
                $msg->addParam(new xmlrpcval($this->userId, "int"));
                $msg->addParam(new xmlrpcval($this->password, "string"));
                $msg->addParam(new xmlrpcval($relation, "string"));
                $msg->addParam(new xmlrpcval("read", "string"));
                $msg->addParam(php_xmlrpc_encode($ids));
                $msg->addParam(php_xmlrpc_encode($fields));
            $val = $this->_cache_request($this->url.'object',$msg);
            
                return php_xmlrpc_decode($val);
        }

      function _cache_request($url,$msg){
         $key =    md5($url.$msg->serialize());

         if(apc_exists($key)){
            $this->cached = true;
            return apc_fetch($key);
         }else{
            $this->cached = false;
            $connection = new xmlrpc_client($url);
             $resp = $connection->send($msg);
            $ret = $resp->value();
             apc_add($key,$ret,2);
            return $ret;         
         }
         
         

      }
}
// Tools
function dump_array($arr){
   echo "<table border=1>";
   foreach ($arr as $c) {
      $i=0;
      $cols=10;
      foreach($c as $property => $value)  { 
         $col = $i%$cols;
         if($col==0 && $i>0) echo "</tr>";
         if($col==0 ) echo "<tr>";
          echo "<td>$property</td><td>$value</td>";
         $i++;
      }
      echo "</tr>";
   }
   echo "</table>";
}

?>

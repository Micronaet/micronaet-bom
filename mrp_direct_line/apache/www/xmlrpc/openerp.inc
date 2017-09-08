<?php
/*$user      = 'admin';
$password  = '30mcrt983';
$dbname    = 'poliambulatorio';
$server_url = 'http://192.168.100.71:8069/xmlrpc/';
$userId    = -1;*/

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
                $sock = new xmlrpc_client($this->url.'common');
                $msg = new xmlrpcmsg('login');
                $msg->addParam(new xmlrpcval($this->database, "string"));
                $msg->addParam(new xmlrpcval($this->user, "string"));
                $msg->addParam(new xmlrpcval($this->password, "string"));
		$resp = $sock->send($msg);
		$val = $resp->value();
		$this->userId = $val->scalarval(); 

            if($this->userId > 0) {
               return $this->userId;
            }else{
               echo '<br><br><br><h2 align=center>Connessione fallita....</h2>';
               die();
            }
        }

        function search($model,$domain){
                $msg = new xmlrpcmsg('execute');
                $msg->addParam(new xmlrpcval($this->database, "string"));
                $msg->addParam(new xmlrpcval($this->userId, "int"));
                $msg->addParam(new xmlrpcval($this->password, "string"));
                $msg->addParam(new xmlrpcval($model, "string"));
                $msg->addParam(new xmlrpcval("search", "string"));
                $msg->addParam(php_xmlrpc_encode($domain));
            $val = $this->_cache_request($this->url.'object',$msg);
            
                return php_xmlrpc_decode($val);
        }

        function read_id($model, $id, $fields=array()){
                $sock = new xmlrpc_client($this->url.'object');
                $msg = new xmlrpcmsg('execute');
                $msg->addParam(new xmlrpcval($this->database, "string"));
                $msg->addParam(new xmlrpcval($this->userId, "int"));
                $msg->addParam(new xmlrpcval($this->password, "string"));
                $msg->addParam(new xmlrpcval($model, "string"));
                $msg->addParam(new xmlrpcval("read", "string"));
                $msg->addParam(new xmlrpcval($id, "string"));
                $msg->addParam(new xmlrpcval($fields, "array"));
                $resp = $sock->send($msg);
		if ($resp->faultCode()) {
		  echo 'Errore: '.$resp->faultString()."<br>";
		} 
                else {
 		   $val=$resp->value();
 		   $res_ids=$val->scalarval();
 		   $id=$res_ids[0]->scalarval();
		   //echo "Paziente: ".$id['name']->scalarval()."<br>";
		   //echo "ID paziente: ".$id['id']->scalarval()."<br>";
		}
        }

        function read_ids($model, $ids, $fields=array()){
                $sock = new xmlrpc_client($this->url.'object');
                $msg = new xmlrpcmsg('execute');
                $msg->addParam(new xmlrpcval($this->database, "string"));
                $msg->addParam(new xmlrpcval($this->userId, "int"));
                $msg->addParam(new xmlrpcval($this->password, "string"));
                $msg->addParam(new xmlrpcval($model, "string"));
                $msg->addParam(new xmlrpcval("read", "string"));
                $msg->addParam(new xmlrpcval($ids, "string"));
                $msg->addParam(new xmlrpcval($fields, "array"));
                $resp = $sock->send($msg);
		if ($resp->faultCode()) {
		  echo 'Errore: '.$resp->faultString()."<br>";
		} 
                else {
 		   $val=$resp->value();
 		   $res_ids=$val->scalarval();
 		   $id=$res_ids[0]->scalarval();
		   //echo "Paziente: ".$id['name']->scalarval()."<br>";
		   //echo "ID paziente: ".$id['id']->scalarval()."<br>";
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

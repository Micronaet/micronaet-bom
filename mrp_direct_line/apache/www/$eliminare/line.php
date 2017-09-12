<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<?php
    ini_set('display_errors', 'Off');
?>

<html>
<head>
<title>Gestione linea</title>
<meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1">
<script language="JavaScript">

</script>
<style type="text/css">
<!--
body {
	margin: 0px;
    font-size: 12px; 
    color: #333333; 
    }

div {
    margin: 0px;
    font-size: 12px;     
    color: #2E9AFE;
    }
    
table {
  	border: 1px solid black;
  	width: 600px;
    font-size: 11px; 
    margin: 5px;
    border-spacing: 0px;
    }

table th {
	background-color: #6E6E6E;
    border: 1px solid black;
	padding: 0px;
    font-size: 12px; 
    color: #FFFFFF;
    text-align: center;
    border-spacing: 0px;
    }

table td {
    text-align: center;
    border: 1px solid black;
    border-spacing: 0px;
    }

table tr {
	background-color: #EEEEEE;
    color: #333333;
    border: 1px solid black;
    padding: 5px;
    border-spacing: 0px;
    }

-->
</style>
</head>
<body>

<?php
include('xmlrpc/xmlrpc.inc');

// PARAMETER:
$user = 'admin';
$password = 'admin';
$dbname = 'Fiam';
$server = 'localhost';
$port = '8069';
$type_connection = 'http';
$server_url = "http://$server:$port/xmlrpc";

// LOGIN:
$sock = new xmlrpc_client("$server_url/common");

$msg = new xmlrpcmsg("login");
$msg->addParam(new xmlrpcval($dbname, "string"));
$msg->addParam(new xmlrpcval($user, "string"));
$msg->addParam(new xmlrpcval($password, "string"));
$resp = $sock->send($msg);
$val = $resp->value();
$uid = $val->scalarval(); 


// READ:
// Leggo i dati del paziente
$partner_id = 1;//$_GET['id'];
$args_read = array(
   new xmlrpcval("id", "string"),
   new xmlrpcval("name", "string"),
);

$sock = new xmlrpc_client("$server_url/object");
$msg=new xmlrpcmsg('execute');
$msg->addParam(new xmlrpcval($dbname, "string"));
$msg->addParam(new xmlrpcval($uid, "int"));
$msg->addParam(new xmlrpcval($password, "string"));
$msg->addParam(new xmlrpcval("res.partner", "string"));
$msg->addParam(new xmlrpcval("read", "string"));
$msg->addParam(new xmlrpcval(array(new xmlrpcval($partner_id, "int")), "array"));
$msg->addParam(new xmlrpcval($args_read, "array"));

$resp = $sock->send($msg);
if ($resp->faultCode()) {
    echo 'Errore: '.$resp->faultString()."\n";
    } 
else {
    $val=$resp->value();
    $ids=$val->scalarval();
    $id=$ids[0]->scalarval();
    $descrizione_patiente= "<div class='title'>Partner: ".$id['name']->scalarval()."</div>";
    //echo "ID paziente: ".$id['id']->scalarval()."<br>";
    }
?>
<?php
    echo $descrizione_patiente;

// SEARCH:
// Cerco le operazioni
/*$args_search=array(
                  new xmlrpcval(
                      array(
                         new xmlrpcval("partner_id" , "string"),
                         new xmlrpcval("=","string"),
                         new xmlrpcval($partner_id,"int")),
                  "array"),
                  );

$sock = new xmlrpc_client("$server_url/object");
$msg=new xmlrpcmsg('execute');
$msg->addParam(new xmlrpcval($dbname, "string"));
$msg->addParam(new xmlrpcval($uid, "int"));
$msg->addParam(new xmlrpcval($password, "string"));
$msg->addParam(new xmlrpcval("dentist.operation", "string"));
$msg->addParam(new xmlrpcval("search", "string"));
$msg->addParam(new xmlrpcval($args_search, "array"));

//print "<PRE>" . htmlentities($msg->serialize()) . "</PRE>";

$resp = $sock->send($msg);
if ($resp->faultCode()) {
   echo 'Error: '.$resp->faultString()."\n";
   } 
else {
   $val=$resp->value();
   $ids=$val->scalarval();
}

// Leggo le operazioni appena cercate:
$args_read=array(
   new xmlrpcval("id", "string"),
   new xmlrpcval("name", "string"),
   new xmlrpcval("date", "string"),
   new xmlrpcval("product_id", "string"),
   new xmlrpcval("tooth", "string"),
   new xmlrpcval("state", "string"),
   new xmlrpcval("note", "string"),
);

$sock = new xmlrpc_client("$server_url/object");
$msg=new xmlrpcmsg('execute');
$msg->addParam(new xmlrpcval($dbname, "string"));
$msg->addParam(new xmlrpcval($uid, "int"));
$msg->addParam(new xmlrpcval($password, "string"));
$msg->addParam(new xmlrpcval("dentist.operation", "string"));
$msg->addParam(new xmlrpcval("read", "string"));
$msg->addParam(new xmlrpcval($ids, "array"));
$msg->addParam(new xmlrpcval($args_read, "array"));

//print "<PRE>" . htmlentities($msg->serialize()) . "</PRE>";

$operazioni_denti=array("11"=>"","12"=>"","13"=>"","14"=>"","15"=>"","16"=>"","17"=>"","18"=>"",
						"21"=>"","22"=>"","23"=>"","24"=>"","25"=>"","26"=>"","27"=>"","28"=>"",
						"31"=>"","32"=>"","33"=>"","34"=>"","35"=>"","36"=>"","37"=>"","38"=>"", 
						"41"=>"","42"=>"","43"=>"","44"=>"","45"=>"","46"=>"","47"=>"","48"=>"", 
						"51"=>"","52"=>"","53"=>"","54"=>"","55"=>"","56"=>"","57"=>"","58"=>"", 
						"61"=>"","62"=>"","63"=>"","64"=>"","65"=>"","66"=>"","67"=>"","68"=>"", 
						"71"=>"","72"=>"","73"=>"","74"=>"","75"=>"","76"=>"","77"=>"","78"=>"", 
						"81"=>"","82"=>"","83"=>"","84"=>"","85"=>"","86"=>"","87"=>"","88"=>"",
                        "*"=>"", "n"=>"");



$resp = $sock->send($msg);
if ($resp->faultCode()) {
  echo 'Error: '.$resp->faultString()."\n";
} else {
  $val=$resp->value();
  $ids=$val->scalarval();
  $id=$ids[0]->scalarval();
  echo "<br><br>";

  foreach ($ids as $item){     
     $elemento=$item->scalarval();
     $prodotto=$elemento['product_id']->scalarval();
     $dente=$elemento['tooth']->scalarval();
     if ($elemento['tooth']){ // solo quelle che hanno i denti TODO controllare se il codice dente è corretto (anche no)!
		 if (is_array($prodotto)) {
            $prodotto_desc=$prodotto[1]->scalarval();
            }
         else {
            $prodotto_desc="Non trovato";
            }

		 $operazioni_denti[$dente] = $operazioni_denti[$dente].
                                        "<tr><td>".$elemento['date']->scalarval().
                                        "</td><td>".$prodotto_desc.
                                        "</td><td>".$elemento['name']->scalarval().
                                        "</td><td>".$elemento['note']->scalarval().
                                        "</td><td><img src='images/".$elemento['state']->scalarval().".gif'>".
                                        "</td></tr>";
     }
   }

}
  echo "<br><br>";

echo "<div class='title'>Elenco operazioni:<div>";
foreach ($operazioni_denti as $dente=>$operazioni){
    if (!(($dente == "56") or ($dente == "57") or ($dente == "58") or 
          ($dente == "66") or ($dente == "67") or ($dente == "68") or 
          ($dente == "76") or ($dente == "77") or ($dente == "78") or 
          ($dente == "86") or ($dente == "87") or ($dente == "88")))
          echo "<div class='mid' id='$dente' style='DISPLAY: none' >";
          if ($operazioni){
             echo "<table> 
                     <tr><th colspan='5'>Dente n.: $dente</th></tr>
                     <tr><th>Data</th> <th>Prodotto</th> <th>Operazione</th> <th>Note</th> <th>Stato</th></tr>
                      $operazioni
                   </table>";
             }
          echo "</div>";
}
*/
?>

</body>
</html>


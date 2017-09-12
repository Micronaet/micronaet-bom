<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<?php
    include_once('config.inc.php');
    include('xmlrpc/xmlrpc.inc');

    // Show error:
    ini_set('display_errors', 'On');
    
    // Autorefresh parameters:
    $page = "";//$_SERVER['PHP_SELF'];
    $sec = "20";

    // ----------------------------------------------------------------------------
    // LOGIN 
    // ----------------------------------------------------------------------------
    $sock = new xmlrpc_client("$server_url/common");
    $msg = new xmlrpcmsg("login");
    $msg->addParam(new xmlrpcval($dbname, "string"));
    $msg->addParam(new xmlrpcval($user, "string"));
    $msg->addParam(new xmlrpcval($password, "string"));
    $resp = $sock->send($msg);
    $val = $resp->value();
    $uid = $val->scalarval(); 

    // ----------------------------------------------------------------------------
    // READ:
    // ----------------------------------------------------------------------------
    // Leggo i dati del paziente
    $aggiornamento = "Aggiornato alle: ".date("h:i:sa");
    $redirect_url =  'http://'.$_SERVER['HTTP_HOST'].$_SERVER['REQUEST_URI'];
    $line_code = $_GET['linea'];

    $args_read = array(
        new xmlrpcval("html", "string"),
        );

    $sock = new xmlrpc_client("$server_url/object");
    $msg = new xmlrpcmsg('execute');
    $msg->addParam(new xmlrpcval($dbname, "string"));
    $msg->addParam(new xmlrpcval($uid, "int"));
    $msg->addParam(new xmlrpcval($password, "string"));
    $msg->addParam(new xmlrpcval("mrp.production.stats", "string"));
    $msg->addParam(new xmlrpcval("get_xmlrpc_html", "string"));
    $msg->addParam(new xmlrpcval($line_code, "string"));
    $msg->addParam(new xmlrpcval($redirect_url, "string"));
    //$msg->addParam(new xmlrpcval(array(new xmlrpcval($line_id, "int")), "array"));
    //$msg->addParam(new xmlrpcval($args_read, "array"));

    $resp = $sock->send($msg);
    $html = "";
    if ($resp->faultCode()) {
        echo 'Errore: '.$resp->faultString()."\n";
        } 
    else {
        $val = $resp->value();
        $html = $val->scalarval(); 
       }
?>
<html>
    <head>
        <title>Gestione linea</title>

        <meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1">
        <meta http-equiv="refresh" content="<?php echo $sec?>;URL='<?php echo $page?>'">

        <link type="text/css" rel="stylesheet" href="/styles/linea.css" />

    </head>
<body>
    <?=$html?>
</body>
</html>


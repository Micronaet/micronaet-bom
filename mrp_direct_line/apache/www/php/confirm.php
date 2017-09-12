<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<?php
    include('../config.php');
    include('../xmlrpc/xmlrpc.inc');

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
    // CONFIRM PRODUCTION:
    // ----------------------------------------------------------------------------
    $sol_id = $_GET['sol_id'];
    $redirect_url = $_GET['redirect_url'];
    
    //$args_read = array(new xmlrpcval("html", "string"),);
    $sock = new xmlrpc_client("$server_url/object");
    $msg = new xmlrpcmsg('execute');
    $msg->addParam(new xmlrpcval($dbname, "string"));
    $msg->addParam(new xmlrpcval($uid, "int"));
    $msg->addParam(new xmlrpcval($password, "string"));
    $msg->addParam(new xmlrpcval("mrp.production.stats", "string"));
    $msg->addParam(new xmlrpcval("set_sol_done_xmlrpc", "string"));
    $msg->addParam(new xmlrpcval($sol_id, "int"));

    $resp = $sock->send($msg);
    if ($resp->faultCode()) {
        echo 'Errore: '.$resp->faultString()."\n";
        }
    else {
        $val = $resp->value();
        header('Location: '.$redirect_url);
        exit();
       }
    ?> 
<html>
    <head>
        <meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1">
        <link type="text/css" rel="stylesheet" href="/styles/linea.css" />
    </head>
    <body>    
    </body>
</html>

<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<?php
    // XMLRPC CONNECT PARAMETER:
    include_once($_SERVER['DOCUMENT_ROOT'] . '/config.inc.php');
    // XMLRPC Module:
    include('xmlrpc/xmlrpc.inc');

    // Show error:
    ini_set('display_errors', 'On');

    // ------------------------------------------------------------------------
    // LOGIN
    // ------------------------------------------------------------------------
    $sock = new xmlrpc_client("$server_url/common");
    $msg = new xmlrpcmsg("login");
    $msg->addParam(new xmlrpcval($dbname, "string"));
    $msg->addParam(new xmlrpcval($user, "string"));
    $msg->addParam(new xmlrpcval($password, "string"));
    $resp = $sock->send($msg);
    $val = $resp->value();
    $uid = $val->scalarval();

    // ------------------------------------------------------------------------
    // READ:
    // ------------------------------------------------------------------------
    $args_read = array(
        new xmlrpcval("html", "string"),
        );

    $sock = new xmlrpc_client("$server_url/object");
    $msg = new xmlrpcmsg('execute');
    $msg->addParam(new xmlrpcval($dbname, "string"));
    $msg->addParam(new xmlrpcval($uid, "int"));
    $msg->addParam(new xmlrpcval($password, "string"));
    $msg->addParam(new xmlrpcval("mrp.production.stats", "string"));
    $msg->addParam(new xmlrpcval("get_xmlrpc_lines_html", "string"));

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
        <title>Linee di produzione</title>
        <meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1">
        <link type="text/css" rel="stylesheet" href="/styles/linea.css" />
    </head>
<body>
    <?=$html?>
</body>
</html>


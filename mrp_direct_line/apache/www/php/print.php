<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<?php
    // XMLRPC CONNECT PARAMETER:
    include_once($_SERVER['DOCUMENT_ROOT'] . '/config.inc.php');
    // XMLRPC Module:
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
    //var_dump($_GET);
    //die();
    if (isset($_GET['all'])) {
        $mode = 'all';
        }
    elseif (isset($_GET['internal'])) {
        $mode = 'internal';
        }
    elseif (isset($_GET['external'])) {
        $mode = 'external';
        }

    if (isset($_GET['total'])) {
        $total = $_GET['total'];
        }
    else {
        $total = 0;
        }
    //$mode = $_GET['mode'];
    $sol_id = $_GET['sol_id'];
    $redirect_url = $_GET['redirect_url'];

    //$args_read = array(new xmlrpcval("html", "string"),);
    $sock = new xmlrpc_client("$server_url/object");
    $msg = new xmlrpcmsg('execute');
    $msg->addParam(new xmlrpcval($dbname, "string"));
    $msg->addParam(new xmlrpcval($uid, "int"));
    $msg->addParam(new xmlrpcval($password, "string"));
    $msg->addParam(new xmlrpcval("sale.order.line", "string"));
    $msg->addParam(new xmlrpcval("print_label_from_php", "string"));
    $msg->addParam(new xmlrpcval($sol_id, "int"));
    $msg->addParam(new xmlrpcval($mode, "string"));
    $msg->addParam(new xmlrpcval($total, "int"));

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

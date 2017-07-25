import manager

with manager.MySQLCursor() as cur:
    #cur.execute("UPDATE `tracks` SET `priority`=GREATEST(0, priority-1);")
    cur.execute("UPDATE `tracks` SET `requestcount`=IF(UNIX_TIMESTAMP(NOW())-UNIX_TIMESTAMP(lastrequested) > 3600*24*22, greatest(requestcount - 1, 0), requestcount);")


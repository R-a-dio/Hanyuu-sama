import manager

with manager.MySQLCursor() as cur:
    cur.execute("SELECT * FROM `streamstatus`;")
    if cur.rowcount == 1:
        row = cur.fetchone()
        l = row['listeners']
        dj = row['djid']
    else:
        l = 0
        dj = 0
    cur.execute("INSERT INTO `listenlog` (`listeners`, `dj`) VALUES ('%s', %s);" % (l, dj))

# i did not include the rest as it is not needed.

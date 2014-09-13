
#
#  DO NOT MODIFY THIS SCRIPT WITHOUT NOTIFYING VIN
#  The graph lib has some strange antics that make
#  it necessary to recalibrate the colors when you
#  add a new player type. Please be careful!
#
import streamstatus
import manager
import config
import time
#import CairoPlot

OTHER = 0
WEB = 1 #firefox, safari, chrome, opera, trident
FOOBAR = 2 #foobar2000
WINAMP = 3 #winampmpeg
ITUNES = 4 #itunes
VLC = 5 #vlc
NSPLAYER = 6 #nsplayer
MOBILE = 7 #iphone, android
MPLAYER = 8
MPC = 9

listeners = streamstatus.get_listeners()
players = {"Other": 0,
                   "Web player": 0,
                   "Foobar": 0,
                   "WinAmp": 0,
                   "iTunes": 0,
                   "VLC": 0,
                   "WMP": 0,
                   "Mobile phone": 0,
                   "MPlayer": 0,
                   "MPC": 0}


with manager.MySQLCursor() as cur:
        for listener in listeners:
                ip = listener['ip']
                player = listener['player']
                #cur.execute("select distinct ps.* from playerstats as ps join playerstats as ps2 where ps.lastset=ps2.lastset and ps.player=%s", (player,))
                #cur.execute("SELECT *, unix_timestamp(lastset) as ut FROM `playerstats` WHERE `player`=%s AND UNIX_TIMESTAMP(NOW()) - UNIX_TIMESTAMP(lastset) < 24*3600", (player,))
                #row = None
                #if cur.rowcount == 0:
                cur.execute("INSERT INTO `playerstats` (ip, player, lastset) VALUES (%s, %s, NOW());", (ip, player))
                #else:
                #        row = cur.fetchone()
                #        id = row['id']
                #        lastset = int(row['ut'])
                #        now = int(time.time())
                #        if now - lastset > 3*3600: #update time expired
                #                cur.execute("UPDATE `playerstats` SET lastset=NOW(), player=%s WHERE id=%s;", (player, id))
with manager.MySQLCursor() as cur:
        now = int(time.time())
        cur.execute("DELETE FROM playerstats WHERE UNIX_TIMESTAMP(NOW()) - UNIX_TIMESTAMP(lastset) > 24*3600")
        #cur.execute("SELECT *, unix_timestamp(lastset) as ut FROM `playerstats`;")
        #count = cur.rowcount
        #with manager.MySQLCursor() as cur2:
        #        for row in cur:
        #                time = row['ut']
        #                id = row['id']
        #                if now - time > 4*24*3600: #entry expired
        #                        cur2.execute("DELETE FROM `playerstats` WHERE `id`=%s;", (id,))
with manager.MySQLCursor() as cur:
        cur.execute("SELECT player FROM `playerstats`;")
        for row in cur:
                player = row['player'].lower()
                if ('foobar' in player):
                        players['Foobar'] += 1
                elif ('winampmpeg' in player):
                        players['WinAmp'] += 1
                elif ('itunes' in player):
                        players['iTunes'] += 1
                elif ('nsplayer' in player):
                        players['WMP'] += 1
                elif ('mplayer' in player):
                        players['MPlayer'] += 1
                elif ('videolan' in player) or ('vlc' in player):
                        players['VLC'] += 1
                elif ('android' in player) or ('iphone' in player):
                        players['Mobile phone'] += 1
                elif ('msie 7.0' in player) and ('.net clr' in player):
                        players['MPC'] += 1
                elif ('firefox' in player) or ('trident' in player) or ('opera' in player) or ('safari' in player) or ('chrome' in player) or ('chromium' in player):
                        players['Web player'] += 1
                elif ('hanyuu-sama' in player) or ('icecast' in player) or ('shoutcast' in player):
                        pass
                else:
                        players['Other'] += 1
with manager.MySQLCursor() as cur:
        cur.execute("SELECT COUNT(*) AS c FROM `playerstats`;")
        count = cur.fetchone()['c']
        cur.execute("INSERT INTO `playerstatslog` (playercount, time) VALUES (%s, NOW());", (count,))
print players
print sum(players.values())
quit()
#i don't know why the colors are in the wrong order...
#might have to reorder if another player is added
#ok, order is in counter clockwise from 3 o'clock
colors = [(9.0,0.65,0.7), #itunes
                  (0.4,0.4,0.5), #mpc
                  (0.0,0.0,0.8), #other
                  (0.8,0.18,0.18), #mobile
                  (0.1,0.5,0.24), #winamp
                  (0.0,0.0,0.1), #foobar
                  (0.9,0.7,0.0), #vlc
                  (0.65,0.65,0.85), #wmp
                  (0.0,0.7,0.3), #web
                  (0.45,0.0,0.8)  #mplayer
                 ]
CairoPlot.pie_plot('/home/www/r-a-dio/res/img/players.svg', players, 700, 450, colors=colors)


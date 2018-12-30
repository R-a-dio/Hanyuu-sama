import manager
from PIL import Image, ImageDraw

def avg_single(sublist):
  dj = sublist[0][1]
  l = [x[0] for x in sublist]
  return (sum(l)/len(l), dj)

def avg_run(l, n=2):
  return [avg_single(l[(i*n):(i*n)+n]) for i in range(len(l) / n)]

def hsv_to_rgb(h, s, v):
  h_i = int(h*6)
  f = h*6 - h_i
  p = v * (1 - s)
  q = v * (1 - f*s)
  t = v * (1 - (1 - f) * s)
  if h_i == 0:
    r, g, b = v, t, p
  if h_i == 1:
    r, g, b = q, v, p
  if h_i == 2:
    r, g, b = p, v, t
  if h_i == 3:
    r, g, b = p, q, v
  if h_i == 4:
    r, g, b = t, p, v
  if h_i == 5:
    r, g, b = v, p, q
  return (int(r*256), int(g*256), int(b*256))

grc = 0.618033988749895
def get_color(seed):
  # very random
  return hsv_to_rgb((seed * grc) % 1.0, 0.5, 0.9)

def listener_graph(path, data_amount=2016, factor=1, height=500):
  data = []
  max_l = 0
  with manager.MySQLCursor() as cur:
    # (60*60) / 5 = 720 minutes per 24 hours.
    cur.execute("SELECT listeners, dj FROM listenlog ORDER BY time DESC LIMIT %s", (data_amount,));
    for row in cur:
      l = row['listeners']
      data.append((row['listeners'], row['dj']))
      max_l = max(l, max_l)
  # reverse the list to make it left to right.
  # scaling?
  lst = [x[0] for x in data]
  average = sum(lst)/len(lst)
  data = data[::-1]
  data = avg_run(data, factor)
  width = len(data)
  img = Image.new('RGB', (width, height), color=(220, 220, 220))
  draw = ImageDraw.Draw(img)
  for x in range(0, width, 288):
    draw.line([(x, 0), (x, height)], fill=(0,0,0))
  for x, (l, dj) in enumerate(data):
    draw.line([(x, height-l), (x, height)], fill=get_color(dj))
  for y in range(0, height, 50):
    c = (0, 0, 0) if (y % 100==0) else (200, 200, 200)
    draw.line([(0, y), (width, y)], fill=c)
  draw.line([(0, height-average), (width, height-average)], fill=(255, 0, 0))
  img.save(path)

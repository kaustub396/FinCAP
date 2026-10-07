import io, json, os

base = os.path.dirname(os.path.abspath(__file__))
src = os.path.join(base, "d1c591a2-cd79-451a-8616-00eb016f3b2f_content_list.json")
with io.open(src, encoding="utf-8") as fh:
    data = json.load(fh)

lines = []
for idx, item in enumerate(data):
    if item.get("type") == "image":
        lines.append(u"{0} | {1} | CAP: {2} | FN: {3}".format(
            idx, item.get("img_path"), item.get("image_caption"), item.get("image_footnote")))

with io.open(os.path.join(base, "_imagemap.txt"), "w", encoding="utf-8") as out:
    out.write(u"\n".join(lines))

print("images:", len(lines))

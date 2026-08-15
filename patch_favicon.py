import shutil, streamlit, os

static = os.path.join(os.path.dirname(streamlit.__file__), "static")
shutil.copy("assets/favicon.png", os.path.join(static, "favicon.png"))

index = os.path.join(static, "index.html")
html = open(index).read().replace("<title>Streamlit</title>", "<title>AgroTech Intelligence</title>")
open(index, "w").write(html)
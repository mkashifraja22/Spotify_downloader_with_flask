import os

from flask import Flask, render_template, redirect, url_for, request, send_from_directory, current_app
from project import main
from flask import send_file
from glob import glob
from io import BytesIO
from zipfile import ZipFile

app = Flask(__name__)


def endreiniger(name):
    file_path = os.path.join(current_app.root_path, f'static/mp3/', )
    for root, dirs, files in os.walk(file_path):
        for f in files:
            if not f.endswith(name):
                os.remove(f"{file_path}/{f}")
            else:
                print(f)


@app.route('/', methods=["GET", "POST"])
def hello_world():
    file_path = os.path.join(current_app.root_path, f'static/mp3/', )
    if request.method == "POST":
        url = request.form.get('url')
        title = main(url)
        if len(title) == 1:
            filename = f'{title[0]}.mp3'
            endreiniger(filename)
            return send_from_directory(directory=file_path, path=filename, as_attachment=True)
        else:
            target = file_path
            stream = BytesIO()
            with ZipFile(stream, 'w') as zf:
                for file in glob(os.path.join(target, '*.mp3')):
                    zf.write(file, os.path.basename(file))
            stream.seek(0)
            for file in glob(os.path.join(target, '*.mp3')):
                endreiniger(file)

            return send_file(
                stream,
                as_attachment=True,
                download_name='archive.zip'
            )
    return render_template("index.html")


if __name__ == '__main__':
    app.run(debug=True)

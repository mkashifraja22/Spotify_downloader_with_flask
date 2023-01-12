import os
import re
import shutil
import time
import urllib.request

import requests
import spotipy
from flask import current_app, send_from_directory
from moviepy.editor import *
from mutagen.easyid3 import EasyID3
from mutagen.id3 import APIC, ID3
from pytube import YouTube
from rich.console import Console
from spotipy.oauth2 import SpotifyClientCredentials

SPOTIPY_CLIENT_ID = '09751d0e5c42480d99929a98659bf4d1'
SPOTIPY_CLIENT_SECRET = '7ccbcbd7b1a94006bff87cf07e518711'

client_credentials_manager = SpotifyClientCredentials(
    client_id=SPOTIPY_CLIENT_ID, client_secret=SPOTIPY_CLIENT_SECRET
)
sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)
file_exists_action = ""


def main(url):
    file_path = os.path.join(current_app.root_path, f'static/mp3/', )
    title = []
    url = validate_url(url.strip())
    if "track" in url:
        songs = [get_track_info(url)]
    elif "playlist" in url:
        songs = get_playlist_info(url)

    start = time.time()
    downloaded = 0
    for i, track_info in enumerate(songs, start=1):
        search_term = f"{track_info['artist_name']} {track_info['track_title']} audio"
        video_link = find_youtube(search_term)

        data = download_yt(video_link)
        audio = data['audio_file']
        title.append(data['title'])
        print("audio", audio)
        print("title", title)
        if audio:
            set_metadata(track_info, audio)
            os.replace(audio, f"{file_path}{os.path.basename(audio)}")
            downloaded += 1
        else:
            print("File exists. Skipping...")
    shutil.rmtree(f"{file_path}/tmp")
    end = time.time()
    print()
    os.chdir(f"{file_path}")
    print(f"Download location: {os.getcwd()}")
    return title


def validate_url(sp_url):
    if re.search(r"^(https?://)?open\.spotify\.com/(playlist|track)/.+$", sp_url):
        return sp_url

    raise ValueError("Invalid Spotify URL")


def get_track_info(track_url):
    res = requests.get(track_url)
    if res.status_code != 200:
        raise ValueError("Invalid Spotify track URL")

    track = sp.track(track_url)

    track_metadata = {
        "artist_name": track["artists"][0]["name"],
        "track_title": track["name"],
        "track_number": track["track_number"],
        "isrc": track["external_ids"]["isrc"],
        "album_art": track["album"]["images"][1]["url"],
        "album_name": track["album"]["name"],
        "release_date": track["album"]["release_date"],
        "artists": [artist["name"] for artist in track["artists"]],
    }

    return track_metadata


def get_playlist_info(sp_playlist):
    res = requests.get(sp_playlist)
    if res.status_code != 200:
        raise ValueError("Invalid Spotify playlist URL")
    pl = sp.playlist(sp_playlist)
    if not pl["public"]:
        raise ValueError(
            "Can't download private playlists. Change your playlist's state to public."
        )
    playlist = sp.playlist_tracks(sp_playlist)

    tracks = [item["track"] for item in playlist["items"]]
    tracks_info = []
    for track in tracks:
        track_url = f"https://open.spotify.com/track/{track['id']}"
        track_info = get_track_info(track_url)
        tracks_info.append(track_info)

    return tracks_info


def find_youtube(query):
    phrase = query.replace(" ", "+")
    search_link = "https://www.youtube.com/results?search_query=" + phrase
    count = 0
    while count < 3:
        try:
            response = urllib.request.urlopen(search_link)
            break
        except:
            count += 1
    else:
        raise ValueError("Please check your internet connection and try again later.")

    search_results = re.findall(r"watch\?v=(\S{11})", response.read().decode())
    first_vid = "https://www.youtube.com/watch?v=" + search_results[0]

    return first_vid


def prompt_exists_action():
    """ask the user what happens if the file being downloaded already exists"""
    global file_exists_action
    if file_exists_action == "SA":  # SA == 'Skip All'
        return False
    elif file_exists_action == "RA":  # RA == 'Replace All'
        return True

    while True:
        resp = "RA".upper().strip()
        if resp in ("RA", "SA"):
            file_exists_action = resp
        if resp in ("R", "RA"):
            return True
        elif resp in ("S", "SA"):
            return False
        print("---Invalid response---")


def download_yt(yt_link):
    file_path = os.path.join(current_app.root_path, f'static/mp3/', )
    """download the video in mp3 format from youtube"""
    yt = YouTube(yt_link)
    # remove chars that can't be in a windows file name
    yt.title = "".join([c for c in yt.title if c not in ['/', '\\', '|', '?', '*', ':', '>', '<', '"']])
    # don't download existing files if the user wants to skip them
    exists = os.path.exists(f"{file_path}{yt.title}.mp3")
    if exists and not prompt_exists_action():
        return False

    # download the music
    video = yt.streams.filter(only_audio=True).first()
    vid_file = video.download(output_path=f"{file_path}/tmp")
    # convert the downloaded video to mp3
    base = os.path.splitext(vid_file)[0]
    audio_file = base + ".mp3"
    mp4_no_frame = AudioFileClip(vid_file)
    mp4_no_frame.write_audiofile(audio_file, logger=None)
    mp4_no_frame.close()
    os.remove(vid_file)
    os.replace(audio_file, f"{file_path}/tmp/{yt.title}.mp3")
    audio_file = f"{file_path}/tmp/{yt.title}.mp3"
    print("yt title..........", yt.title)
    return {'audio_file': audio_file, "title": yt.title}


def set_metadata(metadata, file_path):
    """adds metadata to the downloaded mp3 file"""
    mp3file = EasyID3(file_path)

    # add metadata
    mp3file["albumartist"] = metadata["artist_name"]
    mp3file["artist"] = metadata["artists"]
    mp3file["album"] = metadata["album_name"]
    mp3file["title"] = metadata["track_title"]
    mp3file["date"] = metadata["release_date"]
    mp3file["tracknumber"] = str(metadata["track_number"])
    mp3file["isrc"] = metadata["isrc"]
    mp3file.save()

    # add album cover
    audio = ID3(file_path)
    with urllib.request.urlopen(metadata["album_art"]) as albumart:
        audio["APIC"] = APIC(
            encoding=3, mime="image/jpeg", type=3, desc="Cover", data=albumart.read()
        )
    audio.save(v2_version=3)


if __name__ == "__main__":
    file_exists_action = ""
    console = Console()
    main()

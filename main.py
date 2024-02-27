from configparser import ConfigParser
from os import path
from threading import Thread

import flet as ft
import static_ffmpeg
from yt_dlp import YoutubeDL

config_path = path.expanduser("~/.ytdlp_desktop.ini")


def main(page: ft.Page):
    Thread(target=static_ffmpeg.add_paths).start()

    page.title = "yt-dlp Desktop"
    page.window_min_width = 640
    page.window_min_height = 480

    config = ConfigParser()
    config.read(config_path)
    defconfig = config["DEFAULT"]
    defconfig["dir"] = defconfig.get("dir") or path.expanduser("~/Desktop")

    kinds = ["MP3", "動画(MP4)"]

    queue = []

    tab_ref = ft.Ref[ft.DataTable]()
    url_ref = ft.Ref[ft.TextField]()
    kind_ref = ft.Ref[ft.Dropdown]()
    submit_ref = ft.Ref[ft.FilledButton]()

    def ui_disable():
        url_ref.current.disabled = True
        kind_ref.current.disabled = True
        submit_ref.current.disabled = True
        submit_ref.current.text = "読込中..."
        page.update()

    def ui_enable():
        url_ref.current.disabled = False
        kind_ref.current.disabled = False
        submit_ref.current.disabled = False
        submit_ref.current.text = "ダウンロード"
        page.update()

    def progress_hook(d):
        info = d.get("info_dict")
        id = info.get("id")

        status = status_display = d.get("status")
        if status == "downloading":
            status_display = "ダウンロード中"
        elif status == "error":
            status_display = "ダウンロードエラー"
        elif status == "finished":
            status_display = "ダウンロード完了"

        for e in queue:
            if e["id"] == id:
                progress = ""
                if bytes := d.get("downloaded_bytes"):
                    progress += f" {bytes // (1024 * 1024)}MB"
                    if status == "downloading" and (total := d.get("total_bytes")):
                        progress += f" ({1000 * bytes // total / 10}%)"
                if eta := d.get("eta"):
                    progress += f" 残り{int(eta)}秒"
                e["status_el"].value = status_display + progress
                page.update()
                break

    def postprocessor_hook(d):
        info = d.get("info_dict")
        id = info.get("id")

        status = status_display = d.get("status")
        if status == "finished":
            status_display = "全て完了"
        else:
            status_display = "変換中..."
        pass

        for i, e in enumerate(queue):
            if e["id"] == id:
                e["status_el"].value = status_display
                page.update()
                if status == "finished":
                    del queue[i]
                break

    def ydl_opts():
        res = {
            "paths": {"home": defconfig["dir"]},
            "progress_hooks": [progress_hook],
            "postprocessor_hooks": [postprocessor_hook],
        }
        if kind_ref.current.value == "MP3":
            res["format"] = "bestaudio/best"
            res["postprocessors"] = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ]
        else:
            res["format"] = "bestvideo[ext=mp4]+bestaudio/best[ext=mp4]/best"
        return res

    def download(
        ydl: YoutubeDL,
        url: str | None,
        page: ft.Page,
        cancel_ref: ft.Ref[ft.IconButton],
    ):
        if url is not None:
            if cancel_ref.current is not None:
                cancel_ref.current.disabled = False
                page.update()
            ydl.download([url])
            if cancel_ref.current is not None:
                cancel_ref.current.disabled = True
                page.update()

    def url_submit(_):
        try:
            ui_disable()
            with YoutubeDL(ydl_opts()) as ydl:
                url = url_ref.current.value
                kind = kind_ref.current.value
                cancel_ref = ft.Ref[ft.IconButton]()
                retry_ref = ft.Ref[ft.IconButton]()

                if info := ydl.extract_info(url, download=False, process=False):
                    for e in queue:
                        if e["id"] == info["id"]:
                            raise Exception("すでに追加されています")

                    # p = mp.Process(target=download, args=(ydl, url, page, cancel_ref))
                    Thread(target=download, args=(ydl, url, page, cancel_ref)).start()

                    def cancel():
                        cancel_ref.current.disabled = True
                        page.update()
                        # if p.is_alive():
                        #     p.terminate()

                    def retry():
                        cancel()
                        download(ydl, url, page, cancel_ref)

                    status_el = ft.Text("開始しています……")
                    queue.insert(0, {"id": info["id"], "status_el": status_el})
                    tab_ref.current.rows.insert(
                        0,
                        ft.DataRow(
                            [
                                ft.DataCell(ft.Text(info["title"])),
                                ft.DataCell(ft.Text(info["id"])),
                                ft.DataCell(ft.Text(kind)),
                                ft.DataCell(status_el),
                                ft.DataCell(
                                    ft.Row(
                                        [
                                            ft.IconButton(
                                                ft.icons.CANCEL,
                                                cancel_ref,
                                                on_click=lambda _: cancel(),
                                                tooltip="キャンセル",
                                            ),
                                            ft.IconButton(
                                                ft.icons.REFRESH,
                                                retry_ref,
                                                disabled=True,
                                                on_click=lambda _: retry(),
                                                tooltip="再試行",
                                            ),
                                        ]
                                    ),
                                ),
                            ]
                        ),
                    )
            url_ref.current.value = None
        except Exception as e:
            page.dialog = ft.AlertDialog(
                title=ft.Text("エラー"),
                content=ft.Text(str(e)),
                open=True,
            )
            cancel_ref.current.disabled = True
        finally:
            ui_enable()

    save_config_btn_ref = ft.Ref[ft.TextButton]()

    def current_save_config_tooltip():
        return f"現在: {defconfig['dir']}"

    def pick_dir_result(e: ft.FilePickerResultEvent):
        if e.path:
            defconfig["dir"] = e.path
            with open(config_path, "w") as f:
                config.write(f)
            save_config_btn_ref.current.tooltip = current_save_config_tooltip()
            page.update()

    pick_dir_dlg = ft.FilePicker(on_result=pick_dir_result)
    page.overlay.append(pick_dir_dlg)

    page.appbar = ft.AppBar(
        title=ft.Text(page.title, weight=ft.FontWeight.BOLD),
        actions=[
            ft.Container(
                ft.TextButton(
                    "保存先",
                    save_config_btn_ref,
                    icon=ft.icons.SETTINGS,
                    tooltip=current_save_config_tooltip(),
                    height=64,
                    on_click=lambda _: pick_dir_dlg.get_directory_path(
                        dialog_title="保存先を選択",
                        initial_directory=defconfig["dir"],
                    ),
                ),
                padding=8,
            )
        ],
    )

    page.add(
        ft.ListView(
            [
                ft.DataTable(
                    [
                        ft.DataColumn(ft.Text("タイトル")),
                        ft.DataColumn(ft.Text("ID")),
                        ft.DataColumn(ft.Text("種類")),
                        ft.DataColumn(ft.Text("状態")),
                        ft.DataColumn(ft.Text("操作")),
                    ],
                    ref=tab_ref,
                ),
            ],
            expand=True,
        ),
        ft.Row(
            [
                ft.TextField(
                    url_ref,
                    label="動画のURL",
                    expand=True,
                    keyboard_type=ft.KeyboardType.URL,
                    on_submit=url_submit,
                ),
                ft.Dropdown(
                    kind_ref,
                    label="種類",
                    width=128,
                    options=list(map(lambda t: ft.dropdown.Option(t), kinds)),
                    value=kinds[0],
                ),
                ft.FilledButton(
                    "ダウンロード",
                    submit_ref,
                    height=48,
                    on_click=url_submit,
                ),
            ],
        ),
    )


ft.app(target=main)

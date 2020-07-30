import re
import os

from tools import spider
from downloader import BililiContainer
from common.base import repair_filename, touch_dir

info_api = "https://api.bilibili.com/x/player/pagelist?aid={avid}&bvid={bvid}&jsonp=jsonp"
parse_api = "https://api.bilibili.com/x/player/playurl?avid={avid}&cid={cid}&bvid={bvid}&qn={qn}&type=&otype=json"


def get_title(home_url):
    res = spider.get(home_url)
    title = re.search(
        r'<title .*>(.*)_哔哩哔哩 \(゜-゜\)つロ 干杯~-bilibili</title>', res.text).group(1)
    return title

def get_context(home_url):
    context = {
        'avid': '',
        'bvid': ''
    }

    if re.match(r"https?://www.bilibili.com/video/av(\d+)", home_url):
        context['avid'] = re.match(
            r'https?://www.bilibili.com/video/av(\d+)', home_url).group(1)
    elif re.match(r"https?://b23.tv/av(\d+)", home_url):
        context['avid'] = re.match(r"https?://b23.tv/av(\d+)", home_url).group(1)
    elif re.match(r"https?://www.bilibili.com/video/BV(\w+)", home_url):
        context['bvid'] = re.match(
            r"https?://www.bilibili.com/video/BV(\w+)", home_url).group(1)
    elif re.match(r"https?://b23.tv/BV(\w+)", url):
        context['bvid'] = re.match(r"https?://b23.tv/BV(\w+)", home_url).group(1)

    return context

def get_containers(context, video_dir, format, playlist=None):
    avid, bvid = context['avid'], context['bvid']
    containers = []
    info_url = info_api.format(avid=avid, bvid=bvid)
    res = spider.get(info_url)

    for i, item in enumerate(res.json()["data"]):
        file_path = os.path.join(video_dir, repair_filename(
            '{}.mp4'.format(item["part"])))
        if playlist is not None:
            playlist.write_path(file_path)
        containers.append(BililiContainer(
            id=i+1,
            name=item["part"],
            path=file_path,
            meta={
                "avid": avid,
                "bvid": bvid,
                "cid": item["cid"]
            },
            format=format,
        ))
    if playlist is not None:
        playlist.flush()
    return containers

def parse_segments(container, quality_sequence):
    cid, avid, bvid = container.meta["cid"], container.meta["avid"], container.meta["bvid"]

    if container.format == "flv":
        # 检查是否可以下载，同时搜索支持的清晰度，并匹配最佳清晰度
        touch_message = spider.get(parse_api.format(
            avid=avid, cid=cid, bvid=bvid, qn=80)).json()
        if touch_message["code"] != 0:
            print("warn: 无法下载 {} ，原因： {}".format(
                container.name, touch_message["message"]))
            return

        accept_quality = touch_message['data']['accept_quality']
        for qn in quality_sequence:
            if qn in accept_quality:
                break

        parse_url = parse_api.format(avid=avid, cid=cid, bvid=bvid, qn=qn)
        res = spider.get(parse_url)

        for i, segment in enumerate(res.json()['data']['durl']):
            container.append_media(
                id=i+1,
                url=segment["url"],
                qn=qn,
                type="segment",
            )
    elif container.format == "m4s":
        # 检查是否可以下载，同时搜索支持的清晰度，并匹配最佳清晰度
        parse_api_m4s = parse_api + "&fnver=0&fnval=16&fourk=1"
        play_info = spider.get(parse_api_m4s.format(
            avid=avid, cid=cid, bvid=bvid, qn=quality_sequence[0])).json()
        if play_info["code"] != 0:
            print("warn: 无法下载 {} ，原因： {}".format(
                container.name, play_info["message"]))
            return

        if play_info['data'].get('dash') is None:
            raise Exception('该视频尚不支持 H5 source 哦~')

        # accept_quality = play_info['data']['accept_quality']
        accept_quality = set([video['id']
                            for video in play_info['data']['dash']['video']])
        for qn in quality_sequence:
            if qn in accept_quality:
                break

        parse_url = parse_api_m4s.format(avid=avid, cid=cid, bvid=bvid, qn=qn)
        play_info = spider.get(parse_url).json()

        for video in play_info['data']['dash']['video']:
            if video['id'] == qn:
                container.append_media(
                    id=1,
                    url=video['base_url'],
                    qn=qn,
                    type="video"
                )
                break
        for audio in play_info['data']['dash']['audio']:
            container.append_media(
                id=2,
                url=audio['base_url'],
                qn=qn,
                type="audio"
            )
            break

    elif container.format == 'mp4':
        # 检查是否可以下载，同时搜索支持的清晰度，并匹配最佳清晰度
        parse_api_mp4 = parse_api + "&platform=html5&high_quality=1"
        play_info = spider.get(parse_api_mp4.format(
            avid=avid, cid=cid, bvid=bvid, qn=120)).json()
        if play_info["code"] != 0:
            print("warn: 无法下载 {} ，原因： {}".format(
                container.name, play_info["message"]))
            return

        container.append_media(
            id=1,
            url=play_info['data']['durl'][0]['url'],
            qn=play_info['data']['quality'],
            type="audio"
        )
    else:
        print("Unknown format {}".format(container.format))

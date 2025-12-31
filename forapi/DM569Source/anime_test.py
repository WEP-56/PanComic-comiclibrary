#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DM569动漫网站爬虫全功能测试脚本
"""

import sys
import time
from dm569_source import DM569Source


def print_section(title):
    """打印漂亮的分隔线"""
    print(f"\n{'=' * 10} {title} {'=' * 10}\n")


def test_search(source, keyword):
    print_section("1. 测试搜索功能")
    results = source.search(keyword)
    if results:
        print(f"✓ 搜索成功，找到 {len(results)} 个结果")
        # 选取第一个结果作为后续测试对象
        target = results[0]
        print(f"  [目标] ID: {target['id']} | 标题: {target['title']}")
        return target['id']
    else:
        print("✗ 搜索失败或无结果")
        return None


def test_detail(source, vid):
    print_section("2. 测试详情获取")

    # --- 新增：打印 HTML 源码 ---
    url = f"{source.BASE_URL}/video/{vid}.html"
    response = source._request(url)
    html = response.text

    # 保存到本地文件，方便你用 VSCode 或浏览器打开看
    with open(f"debug_{vid}.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✓ HTML 源码已保存到 debug_{vid}.html")

    # --- 打印包含"简介"关键字的行 (帮助我们定位) ---
    # 这部分代码保留，但如果你觉得太长，可以注释掉
    # print("正在扫描包含 '简介'、'主演' 关键字的 HTML 片段...")
    # lines = html.split('\n')
    # for i, line in enumerate(lines):
    #     if '简介' in line or 'intro' in line or 'content' in line or '剧情' in line:
    #         # 打印前后 2 行上下文
    #         start = max(0, i - 2)
    #         end = min(len(lines), i + 3)
    #         print(f"  [第 {i + 1} 行]:")
    #         for j in range(start, end):
    #             prefix = ">>>" if j == i else "   "
    #             print(f"  {prefix} {lines[j]}")
    #         print("-" * 40)
    # ---------------------------------------

    # 原有的详情提取
    detail = source.get_detail(vid)

    # === 新增：打印提取结果 ===
    print_section("详情提取结果")
    if detail['success']:
        print(f"✓ 详情获取成功")
        print(f"  标题: {detail['title']}")
        print(f"  封面: {detail['cover'][:80]}..." if detail['cover'] else "  封面: 无")
        print(f"  简介: {detail['intro'][:100]}..." if detail['intro'] else "  简介: [空]")
        print(f"  别名: {detail.get('alias', '无')}")
        print(f"  标签: {detail['tags']}")
        print(f"  年份: {detail['year']}")
        print(f"  地区: {detail['area']}")
        print(f"  更新: {detail['updated']}")
    else:
        print(f"✗ 详情获取失败")


def test_episodes(source, vid):
    print_section("3. 测试剧集列表获取")
    data = source.get_episodes(vid)

    if data['lines']:
        print("✓ 剧集列表获取成功")
        print(f"  动漫标题: {data['title']}")
        print(f"  线路数量: {len(data['lines'])}")

        for i, line in enumerate(data['lines']):
            print(f"  线路 {i + 1}: {line['name']} (共 {len(line['episodes'])} 集)")
            # 打印前 3 集和最后 1 集
            eps = line['episodes']
            preview_eps = eps[:3]
            if len(eps) > 3:
                preview_eps.append(eps[-1])

            ep_names = [e['name'] for e in preview_eps]
            print(f"    -> 剧集: {', '.join(ep_names)}...")
    else:
        print("✗ 剧情列表获取失败或无数据")


def test_play_url(source, vid):
    print_section("4. 测试视频地址解析 (解密)")

    # 获取第一集，第一条线路
    data = source.get_episodes(vid)
    if not data['lines']:
        print("✗ 跳过测试：无剧集数据")
        return

    # 默认取第 0 条线路
    target_line = data['lines'][0]
    target_ep = target_line['episodes'][0]

    print(f"  目标: {target_line['name']} - {target_ep['name']}")

    video_info = source.get_video_url(vid=vid, line=0, ep=0)

    if video_info['success']:
        print("✓ 视频地址解析成功")
        print(f"  Stream URL: {video_info['stream_url']}")

        m3u8_content = video_info['real_m3u8']
        # 检查内容是否为 M3U8 格式
        if m3u8_content.strip().startswith('#EXT'):
            print(f"  M3U8 内容: 验证通过 (标准 HLS 格式)")
            # 打印前几行看看
            lines = m3u8_content.split('\n')[:3]
            for line in lines:
                if line:
                    print(f"    {line}")
        else:
            print(f"  ⚠ M3U8 内容可能不是标准格式 (首字符: {m3u8_content[:50]})")
    else:
        print(f"✗ 视频地址解析失败: {video_info['error']}")


def main():
    # 初始化
    source = DM569Source()
    keyword = "海贼王"

    if len(sys.argv) > 1:
        keyword = sys.argv[1]

    print(f"🚀 DM569 爬虫全功能测试开始 (搜索词: {keyword})")

    # 1. 搜索
    vid = test_search(source, keyword)
    if not vid:
        return

    # 停顿一下，礼貌爬虫
    time.sleep(1)

    # 2. 详情
    test_detail(source, vid)
    time.sleep(1)

    # 3. 剧集
    test_episodes(source, vid)
    time.sleep(1)

    # 4. 播放地址 (最关键)
    test_play_url(source, vid)

    print("\n🎉 所有测试完成！")


if __name__ == "__main__":
    main()

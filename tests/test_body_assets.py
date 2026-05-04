from app.publishers.body_assets import insert_header_image_after_first_blockquote


def test_insert_header_image_after_first_blockquote_places_image_after_quote_block():
    markdown = (
        "# 标题\n\n"
        "> 账号定位：技术小甜甜（new-main）\n"
        "> 今日目标：traffic\n"
        "> 专栏/系列：技术前沿每日速读\n\n"
        "正文第一段\n"
    )

    result = insert_header_image_after_first_blockquote(
        markdown,
        "![技术前沿每日速读头图](https://example.com/trend.jpg)",
    )

    assert "> 专栏/系列：技术前沿每日速读\n\n![技术前沿每日速读头图](https://example.com/trend.jpg)\n\n正文第一段" in result


def test_insert_header_image_after_first_blockquote_is_idempotent():
    markdown = (
        "# 标题\n\n"
        "> 引文\n\n"
        "![技术前沿每日速读头图](https://example.com/trend.jpg)\n\n"
        "正文\n"
    )

    result = insert_header_image_after_first_blockquote(
        markdown,
        "![技术前沿每日速读头图](https://example.com/trend.jpg)",
    )

    assert result.count("![技术前沿每日速读头图](https://example.com/trend.jpg)") == 1

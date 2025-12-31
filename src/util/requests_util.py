import requests


def post(url, params=None):
    """
    发送 POST 请求。

    :param url: 请求 URL
    :param params: (可选) JSON 数据
    :return: Response 对象
    """
    try:
        response = requests.post(url, json=params)
        response.raise_for_status()  # 如果响应状态码不是 200，则抛出异常
        return response
    except requests.RequestException as e:
        print(f"请求失败: {e}")
        return None


def get(url, params=None):
    """
    发送 GET 请求。

    :param url: 请求 URL
    :param params: (可选) 查询参数
    :return: Response 对象
    """
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response
    except requests.RequestException as e:
        print(f"请求失败: {e}")
        return None


def delete(url, params=None):
    """
    发送 DELETE 请求。

    :param url: 请求 URL
    :param params: (可选) 表单数据
    :return: Response 对象
    """
    try:
        response = requests.delete(url, params=params)
        response.raise_for_status()
        return response
    except requests.RequestException as e:
        print(f"请求失败: {e}")
        return None

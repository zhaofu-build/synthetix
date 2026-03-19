"""API 响应模型单元测试"""
import pytest
from src.model.response import (
    APIResponse,
    PaginatedResponse,
    ErrorResponse,
    success_response,
    error_response,
    paginated_response
)


class TestAPIResponse:
    """API响应模型测试"""

    def test_success_response_default(self):
        """测试默认成功响应"""
        response = APIResponse()
        assert response.success is True
        assert response.code == 200
        assert response.message == ""
        assert response.data is None
        assert response.timestamp > 0

    def test_success_response_with_data(self):
        """测试带数据的成功响应"""
        data = {"id": 1, "name": "test"}
        response = success_response(data=data, message="操作成功")

        assert response.success is True
        assert response.data == data
        assert response.message == "操作成功"
        assert response.code == 200

    def test_success_response_serialization(self):
        """测试响应序列化"""
        response = success_response(data={"key": "value"}, message="测试")
        serialized = response.model_dump()

        assert serialized["success"] is True
        assert serialized["data"]["key"] == "value"
        assert serialized["message"] == "测试"
        assert "timestamp" in serialized


class TestErrorResponse:
    """错误响应模型测试"""

    def test_error_response_default(self):
        """测试默认错误响应"""
        response = ErrorResponse(
            error="TestError",
            message="测试错误",
            code=500
        )
        assert response.success is False
        assert response.error == "TestError"
        assert response.message == "测试错误"
        assert response.code == 500

    def test_error_response_factory(self):
        """测试错误响应工厂函数"""
        response = error_response(
            error="ValidationError",
            message="参数验证失败",
            code=400
        )

        assert response.success is False
        assert response.error == "ValidationError"
        assert response.message == "参数验证失败"
        assert response.code == 400


class TestPaginatedResponse:
    """分页响应模型测试"""

    def test_paginated_response_empty(self):
        """测试空分页响应"""
        response = PaginatedResponse.create([], 0, 1, 10)

        assert response.items == []
        assert response.total == 0
        assert response.page == 1
        assert response.page_size == 10
        assert response.total_pages == 0

    def test_paginated_response_single_page(self):
        """测试单页分页响应"""
        items = [{"id": 1}, {"id": 2}, {"id": 3}]
        response = PaginatedResponse.create(items, 3, 1, 10)

        assert response.items == items
        assert response.total == 3
        assert response.page == 1
        assert response.page_size == 10
        assert response.total_pages == 1

    def test_paginated_response_multiple_pages(self):
        """测试多页分页响应"""
        items = [{"id": i} for i in range(25)]
        response = PaginatedResponse.create(items, 25, 2, 10)

        assert len(response.items) == 25
        assert response.total == 25
        assert response.page == 2
        assert response.page_size == 10
        assert response.total_pages == 3  # 25 / 10 = 3页

    def test_paginated_response_factory(self):
        """测试分页响应工厂函数"""
        items = [{"name": f"item{i}"} for i in range(5)]
        response = paginated_response(items, 15, 1, 5)

        assert response.items == items
        assert response.total == 15
        assert response.page == 1
        assert response.page_size == 5
        assert response.total_pages == 3


class TestResponseTypeGeneric:
    """测试泛型类型支持"""

    def test_response_with_dict_type(self):
        """测试字典类型响应"""
        class DictResponse(APIResponse[dict]):
            pass

        response = DictResponse(data={"key": "value"})
        assert response.data == {"key": "value"}

    def test_response_with_list_type(self):
        """测试列表类型响应"""
        class ListResponse(APIResponse[list]):
            pass

        data = [1, 2, 3]
        response = ListResponse(data=data)
        assert response.data == data

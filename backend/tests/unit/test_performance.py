# backend/tests/unit/test_performance.py

import time
from backend.src.utils.performance import PerformanceMonitor


def test_measure_operation():
    """작업 시간 측정"""
    monitor = PerformanceMonitor()
    
    with monitor.measure("test_op"):
        time.sleep(0.1)
    
    stats = monitor.get_stats("test_op")
    
    assert stats["count"] == 1
    assert stats["mean"] >= 0.1
    assert stats["mean"] < 0.2  # 여유


def test_multiple_measurements():
    """여러 측정"""
    monitor = PerformanceMonitor()
    
    for _ in range(3):
        with monitor.measure("fast_op"):
            time.sleep(0.05)
    
    stats = monitor.get_stats("fast_op")
    
    assert stats["count"] == 3
    assert stats["mean"] >= 0.05
    assert stats["min"] >= 0.05
    assert stats["max"] < 0.1


def test_get_all_stats():
    """전체 통계"""
    monitor = PerformanceMonitor()
    
    with monitor.measure("op1"):
        time.sleep(0.05)
    
    with monitor.measure("op2"):
        time.sleep(0.1)
    
    all_stats = monitor.get_stats()
    
    assert "op1" in all_stats
    assert "op2" in all_stats
    assert all_stats["op2"]["mean"] > all_stats["op1"]["mean"]


def test_reset():
    """리셋"""
    monitor = PerformanceMonitor()
    
    with monitor.measure("test"):
        pass
    
    assert monitor.get_stats("test")["count"] == 1
    
    monitor.reset()
    
    assert monitor.get_stats("test") == {}
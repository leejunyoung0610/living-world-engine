# backend/src/utils/performance.py

import time
import logging
from contextlib import contextmanager
from typing import Dict, List
from statistics import mean, median

logger = logging.getLogger(__name__)


class PerformanceMonitor:
    """성능 측정 및 모니터링"""
    
    def __init__(self):
        self.measurements: Dict[str, List[float]] = {}
        self.current_operation: str = ""
        self.start_time: float = 0.0
    
    @contextmanager
    def measure(self, operation: str):
        """작업 시간 측정
        
        Usage:
            with perf_monitor.measure("memory_search"):
                results = search(...)
        """
        self.current_operation = operation
        self.start_time = time.time()
        
        try:
            yield
        finally:
            elapsed = time.time() - self.start_time
            
            # 기록
            if operation not in self.measurements:
                self.measurements[operation] = []
            self.measurements[operation].append(elapsed)
            
            # 로깅 (느린 작업은 경고)
            if elapsed > 1.0:
                logger.warning(f"⚠️  {operation}: {elapsed:.3f}s (slow!)")
            else:
                logger.debug(f"✓ {operation}: {elapsed:.3f}s")
    
    def get_stats(self, operation: str = None) -> Dict:
        """통계 반환
        
        Args:
            operation: 특정 작업 (None이면 전체)
        """
        if operation:
            if operation not in self.measurements:
                return {}
            
            times = self.measurements[operation]
            return {
                "operation": operation,
                "count": len(times),
                "total": sum(times),
                "mean": mean(times),
                "median": median(times),
                "min": min(times),
                "max": max(times),
            }
        
        # 전체 통계
        stats = {}
        for op, times in self.measurements.items():
            stats[op] = {
                "count": len(times),
                "mean": mean(times),
                "median": median(times),
                "min": min(times),
                "max": max(times),
            }
        return stats
    
    def print_report(self):
        """성능 리포트 출력"""
        if not self.measurements:
            print("\n📊 No performance data collected\n")
            return
        
        print("\n" + "="*70)
        print("📊 Performance Report")
        print("="*70)
        
        # 작업별 통계
        stats = self.get_stats()
        
        # 평균 시간 순으로 정렬
        sorted_ops = sorted(
            stats.items(), 
            key=lambda x: x[1]['mean'], 
            reverse=True
        )
        
        print(f"\n{'Operation':<30} {'Count':>8} {'Mean':>10} {'Median':>10} {'Max':>10}")
        print("-"*70)
        
        for op, data in sorted_ops:
            count = data['count']
            mean_time = data['mean']
            median_time = data['median']
            max_time = data['max']
            
            # 느린 작업 강조
            if mean_time > 1.0:
                marker = "⚠️ "
            elif mean_time > 0.5:
                marker = "⚡"
            else:
                marker = "✓ "
            
            print(f"{marker}{op:<28} {count:>8} {mean_time:>9.3f}s {median_time:>9.3f}s {max_time:>9.3f}s")
        
        print("="*70 + "\n")
        
        # 병목 경고
        bottlenecks = [(op, data['mean']) for op, data in stats.items() if data['mean'] > 0.5]
        if bottlenecks:
            print("⚠️  Potential Bottlenecks (>0.5s):")
            for op, avg_time in sorted(bottlenecks, key=lambda x: x[1], reverse=True):
                print(f"   - {op}: {avg_time:.3f}s average")
            print()
    
    def reset(self):
        """측정 데이터 초기화"""
        self.measurements.clear()
        logger.info("Performance measurements reset")
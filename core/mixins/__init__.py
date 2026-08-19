# -*- coding: utf-8 -*-
"""Valorant 的 mix-in 集合。

每个模块提供一个 mix-in 类，由 `core.valorant.Valorant` 多继承装配。各 mix-in
必须在自己顶部显式 import 所需依赖，不得依赖 valorant.py 的顶层 import；共享
运行时事实统一从 `core.runtime` 取。
"""

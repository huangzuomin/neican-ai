---
title: Redis Array Playground
date: '2026-05-04T12:00:00+08:00'
slug: 2026-05-04-redis-array-playground-121
type: event
event_type: 模型/产品变化
entities: []
topics:
- llm
sources:
- url: https://simonwillison.net/2026/May/4/redis-array/#atom-everything
  title: Redis Array Playground
  publisher: Simon Willison Blog
timeline:
  date: '2026-05-04'
  year: '2026'
seo:
  description: 'Tool: Redis Array Playground Salvatore Sanfilippo submitted a PR adding
    a new data type - arrays - to Redis. The new commands are ARCOUNT , ARDEL , ARDELRANGE
    , ARGET , ARGETRANGE , ARGREP , ARINFO , ARINSERT , ARLASTITEMS , ARLEN , ARMGET
    , ARMSET , ARNEXT , AROP , ARRING , ARSCAN , ARSEEK , ARS'
---

## 发生了什么

Tool: Redis Array Playground Salvatore Sanfilippo submitted a PR adding a new data type - arrays - to Redis. The new commands are ARCOUNT , ARDEL , ARDELRANGE , ARGET , ARGETRANGE , ARGREP , ARINFO , ARINSERT , ARLASTITEMS , ARLEN , ARMGET , ARMSET , ARNEXT , AROP , ARRING , ARSCAN , ARSEEK , ARS

## 为什么重要

这条信息暂归为背景信号，主要影响 相关产品、模型、公司或开发者生态，并关联 llm。它的价值在于提示后续是否会出现连续的产品、采用、融资、治理或生态变化。

## 证据状态

已保留原文链接；仍需结合后续来源确认影响范围。

## 可验证线索

- Tool: Redis Array Playground Salvatore Sanfilippo submitted a PR adding a new data type - arrays - to Redis
- The new commands are ARCOUNT , ARDEL , ARDELRANGE , ARGET , ARGETRANGE , ARGREP , ARINFO , ARINSERT , ARLASTITEMS , ARLEN , ARMGET , ARMSET , ARNEXT , AROP , ARRING , ARSCAN , ARSEEK , ARSET
- The implementation is currently available in a branch, so I had Claude Code for web build this interactive playground for trying out the new commands in a WASM-compiled build of a subset of Redis running in the browser
- The most interesting new command is ARGREP which can run a server-side grep against a range of values in the array using the newly vendored TRE regex library

## 下一步观察

- 原文或官方后续是否给出更完整细节。
- 是否出现第二来源、客户采用、开发者反馈或反向信号。
- 是否足以改变相关主题页或时间线的当前判断。

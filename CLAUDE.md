# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a study/experimentation project for working with the [OpenRouter](https://openrouter.ai) API, which provides unified access to multiple LLM providers.

## Configuration

- **`.env.txt`** — Contains the `OPENROUTER_API_KEY`. Rename to `.env` before use and ensure it is gitignored.
- **`model.txt`** — Lists OpenRouter model IDs to experiment with (e.g., `google/gemma-4-31b-it:free`, `openai/gpt-oss-120b:free`).

## OpenRouter API

OpenRouter exposes an OpenAI-compatible REST API. Base URL: `https://openrouter.ai/api/v1`. Authenticate with `Authorization: Bearer $OPENROUTER_API_KEY`. Model IDs follow the `provider/model-name` format as listed in `model.txt`.

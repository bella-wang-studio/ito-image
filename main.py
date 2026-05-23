from __future__ import annotations

import argparse
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any

from src import chat as chat_client
from src import generate_image as image_client


PROJECT_ROOT = Path(__file__).resolve().parent
SOURCE_DIR = PROJECT_ROOT / "source"
PRODUCT_DIR = SOURCE_DIR / "产品"
MODEL_DIR = SOURCE_DIR / "模特"
REFERENCE_DIR = SOURCE_DIR / "参考图"
LOG_DIR = PROJECT_ROOT / "logs"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
MAX_IMAGE_INPUTS = 16
MAX_CHAT_ATTEMPTS = 3
MAX_REFERENCE_STYLE_IMAGES = 5
DEFAULT_IMAGE_GENERATION_COUNT = 9
IMAGE_GENERATION_COUNT_ENV = "IMAGE_GENERATION_COUNT"
IMAGE_PROMPT_GUARDRAILS = """
Critical generation guardrails:
- Preserve accurate physical scale: the prompt must explicitly include the model height and product length x width x height from the dimension reference, and the generated image must strictly follow those measurements. The product must not look too small or too large.
- Study the attached product images carefully and keep the exact product shape, structure, proportions, material behavior, color, hardware, seams, straps, handles, openings, and other visible construction details. Do not invent, simplify, redesign, or modify the product's silhouette or structure.
- Keep perspective relationships physically coherent: the model, product, hands, body contact points, horizon, lens angle, shadows, reflections, and scene depth must align naturally with one another. Avoid mismatched perspective, impossible attachment points, or floating/warped product placement.
- Do not add poster-like typography, graphic slogans, title text, captions, promotional copy, UI, watermarks, or decorative text overlays. Existing text that naturally belongs to the real scene or the product may remain, but no added poster text.
""".strip()


@dataclass(frozen=True)
class ProductOption:
    product: str
    color: str
    color_path: Path
    front_image: Path
    images: list[Path]
    description_path: Path | None


@dataclass(frozen=True)
class ModelOption:
    name: str
    image_path: Path
    description_path: Path | None


@dataclass(frozen=True)
class ChatConfig:
    base_url: str
    api_key: str
    model: str


@dataclass(frozen=True)
class ImageConfig:
    base_url: str
    api_key: str
    model: str


class RunLogger:
    def __init__(self) -> None:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        self.timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.path = LOG_DIR / f"{self.timestamp}.log"
        self._lock = Lock()
        self.write("运行开始", f"日志文件：{self.path}")

    def write(self, title: str, content: str | None = None) -> None:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines = [f"\n{'=' * 80}", f"[{now}] {title}"]
        if content:
            lines.append(content.rstrip())
        text = "\n".join(lines) + "\n"
        with self._lock:
            with self.path.open("a", encoding="utf-8") as file:
                file.write(text)

    def write_json(self, title: str, data: Any) -> None:
        self.write(title, json.dumps(data, ensure_ascii=False, indent=2, default=str))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="按产品、模特和参考图自动生成图片。")
    parser.add_argument("--size", default="3:4", help="画面比例或像素尺寸，默认 3:4")
    parser.add_argument(
        "--resolution",
        default="1k",
        choices=("1k", "2k", "4k"),
        help="分辨率档位，默认 1k",
    )
    parser.add_argument(
        "--official-fallback",
        action="store_true",
        help="生图请求失败时允许使用官方渠道兜底",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=180,
        help="每个生图任务轮询超时时间秒数，默认 180",
    )
    parser.add_argument(
        "--initial-delay",
        type=float,
        default=10,
        help="提交生图任务后首次查询前等待秒数，默认 10",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=5,
        help="生图任务轮询间隔秒数，默认 5",
    )
    return parser.parse_args()


def load_configs() -> tuple[ChatConfig, ImageConfig]:
    chat_client.load_dotenv()
    image_client.load_dotenv()

    chat_config = ChatConfig(
        base_url=require_env("CHAT_BASE_URL"),
        api_key=require_env("CHAT_API_KEY"),
        model=require_env("CHAT_MODEL"),
    )
    image_config = ImageConfig(
        base_url=require_env("IMAGE_BASE_URL"),
        api_key=require_env("IMAGE_API_KEY"),
        model=require_env("IMAGE_MODEL"),
    )
    return chat_config, image_config


def load_generation_count() -> int:
    raw = os.getenv(IMAGE_GENERATION_COUNT_ENV)
    if raw is None or not raw.strip():
        return DEFAULT_IMAGE_GENERATION_COUNT
    try:
        count = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{IMAGE_GENERATION_COUNT_ENV} 必须是正整数。") from exc
    if count <= 0:
        raise RuntimeError(f"{IMAGE_GENERATION_COUNT_ENV} 必须大于 0。")
    return count


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"请先在环境变量或 .env 中设置 {name}。")
    return value


def discover_products() -> list[ProductOption]:
    options: list[ProductOption] = []
    for product_dir in visible_dirs(PRODUCT_DIR):
        description_path = find_product_description(product_dir.name)

        for color_dir in visible_dirs(product_dir):
            images = sorted(image_files(color_dir), key=lambda path: path.as_posix())
            if not images:
                continue
            front_image = find_front_image(color_dir, images)
            options.append(
                ProductOption(
                    product=product_dir.name,
                    color=color_dir.name,
                    color_path=color_dir,
                    front_image=front_image,
                    images=images,
                    description_path=description_path,
                )
            )
    return sorted(options, key=lambda option: (option.product, option.color))


def find_product_description(product_name: str) -> Path | None:
    candidates = [product_name]
    base_name = re.sub(r"\s+\d+\s*(?:inch|in)\s*$", "", product_name, flags=re.I)
    if base_name != product_name:
        candidates.append(base_name)

    for candidate in candidates:
        path = PRODUCT_DIR / f"{candidate}.md"
        if path.exists():
            return path
    return None


def discover_models() -> list[ModelOption]:
    models: list[ModelOption] = []
    for image_path in sorted(image_files(MODEL_DIR), key=lambda path: path.name):
        description_path = image_path.with_suffix(".md")
        models.append(
            ModelOption(
                name=image_path.stem,
                image_path=image_path,
                description_path=description_path if description_path.exists() else None,
            )
        )
    return models


def visible_dirs(path: Path) -> list[Path]:
    if not path.exists():
        return []
    return sorted(
        child for child in path.iterdir() if child.is_dir() and not child.name.startswith(".")
    )


def image_files(path: Path) -> list[Path]:
    if not path.exists():
        return []
    return [
        child
        for child in path.rglob("*")
        if child.is_file()
        and not any(part.startswith(".") for part in child.parts)
        and child.suffix.lower() in IMAGE_SUFFIXES
    ]


def find_front_image(color_dir: Path, images: list[Path]) -> Path:
    direct_matches = [
        color_dir / f"正面{suffix}" for suffix in (".jpg", ".jpeg", ".png", ".webp")
    ]
    for path in direct_matches:
        if path.exists():
            return path

    for path in images:
        if path.stem == "正面":
            return path
    return images[0]


def call_chat(
    config: ChatConfig,
    prompt: str,
    image_files: list[Path] | None = None,
    logger: RunLogger | None = None,
    label: str = "chatpy 请求",
) -> str:
    image_paths = [str(path) for path in image_files or []]
    if logger:
        logger.write(
            f"{label} - 发送",
            "\n".join(
                [
                    f"模型：{config.model}",
                    "图片：",
                    *(image_paths or ["无"]),
                    "",
                    "提示词：",
                    prompt,
                ]
            ),
        )

    reply = chat_client.chat(
        prompt=prompt,
        image_urls=None,
        image_files=image_paths,
        base_url=config.base_url,
        api_key=config.api_key,
        model=config.model,
    )
    if logger:
        logger.write(f"{label} - 回复", reply)
    return reply


def match_product_with_ai(
    user_idea: str,
    products: list[ProductOption],
    config: ChatConfig,
    logger: RunLogger,
) -> ProductOption | None:
    inventory: dict[str, list[str]] = {}
    for option in products:
        inventory.setdefault(option.product, []).append(option.color)

    prompt = f"""
你是一个严谨的商品目录匹配器。
根据用户的一句话，从产品目录中判断用户想使用哪个产品、哪个颜色。

用户的话：
{user_idea}

产品目录：
{json.dumps(inventory, ensure_ascii=False, indent=2)}

要求：
- 只能选择目录里真实存在的 product 和 color，必须完全照抄目录名称。
- 如果用户没有明确表达产品或颜色，或者存在多个合理选项，返回 matched=false。
- 只返回 JSON，不要解释。

JSON 格式：
{{"matched": true, "product": "产品名", "color": "颜色名"}}
或
{{"matched": false, "product": "", "color": ""}}
""".strip()
    data = call_chat_for_json(
        config,
        prompt,
        lambda value: validate_product_match(value, products),
        logger=logger,
        label="第1步 产品和颜色匹配",
    )
    logger.write_json("第1步 产品和颜色匹配 - 解析结果", data)
    if not data.get("matched"):
        return None
    matched = find_product(products, str(data.get("product", "")), str(data.get("color", "")))
    logger.write_json("第1步 产品和颜色匹配 - 最终结果", product_log_data(matched))
    return matched


def match_model_with_ai(
    user_idea: str,
    models: list[ModelOption],
    config: ChatConfig,
    logger: RunLogger,
) -> ModelOption | None:
    model_payload = [
        {
            "name": model.name,
            "description": read_text(model.description_path),
        }
        for model in models
    ]
    prompt = f"""
你是一个严谨的模特目录匹配器。
根据用户的一句话，从模特目录中判断用户想使用哪位模特。

用户的话：
{user_idea}

模特目录：
{json.dumps(model_payload, ensure_ascii=False, indent=2)}

要求：
- 只能选择目录里真实存在的 name，必须完全照抄目录名称。
- 如果用户没有明确表达模特，或者存在多个合理选项，返回 matched=false。
- 只返回 JSON，不要解释。

JSON 格式：
{{"matched": true, "model": "模特名"}}
或
{{"matched": false, "model": ""}}
""".strip()
    data = call_chat_for_json(
        config,
        prompt,
        lambda value: validate_model_match(value, models),
        logger=logger,
        label="第2步 模特匹配",
    )
    logger.write_json("第2步 模特匹配 - 解析结果", data)
    if not data.get("matched"):
        return None
    matched = find_model(models, str(data.get("model", "")))
    logger.write_json("第2步 模特匹配 - 最终结果", model_log_data(matched))
    return matched


def reverse_reference_style(config: ChatConfig, logger: RunLogger) -> str:
    references = sorted(image_files(REFERENCE_DIR), key=lambda path: path.name)
    if not references:
        raise RuntimeError("source/参考图 下没有可用图片。")
    selected_references = references[:MAX_REFERENCE_STYLE_IMAGES]
    logger.write_json(
        "第3步 参考图风格反推 - 参考图选择",
        {
            "available": [str(path) for path in references],
            "selected": [str(path) for path in selected_references],
            "max_selected": MAX_REFERENCE_STYLE_IMAGES,
        },
    )

    prompt = """
Analyze the attached reference image(s) together and reverse-engineer one unified set of visual style attributes.
Return a concise English style prompt for image generation based on the shared style across the references.

Focus on mood, lighting, color palette, composition, lens/camera feeling, texture, styling,
production design, and editorial/art direction.
Do not describe the exact subject identity or copy the scene literally.
Leave room for creative variation while preserving the reference tone.
Return only the English style prompt.
""".strip()
    style_prompt = call_chat(
        config,
        prompt,
        selected_references,
        logger=logger,
        label="第3步 参考图风格反推",
    ).strip()
    logger.write("第3步 参考图风格反推 - 最终风格提示词", style_prompt)
    return style_prompt


def generate_image_prompts(
    user_idea: str,
    product: ProductOption,
    model: ModelOption,
    style_prompt: str,
    count: int,
    config: ChatConfig,
    logger: RunLogger,
) -> list[str]:
    dimension_reference = build_dimension_reference(product, model)
    prompt = f"""
You are an expert commercial fashion and travel accessory image prompt writer.
Create {count} distinct English image-generation prompts.

User idea:
{user_idea}

Reference style prompt:
{style_prompt}

Selected product:
- product: {product.product}
- color: {product.color}
- product description:
{read_text(product.description_path)}

Selected model:
- model: {model.name}
- model description:
{read_text(model.description_path)}

Required dimension reference:
{dimension_reference}

Attached images:
- product front image for exact product/color appearance
- model image for the selected model's appearance

Prompt requirements:
- Each prompt must be in English.
- Each prompt must feature the selected model and the selected product in the selected color.
- Preserve the reference image's tone, mood, lighting, styling, and art direction, but create fresh scenes.
- Keep the product visually clear and believable.
- Every prompt must explicitly quote the Required dimension reference, including the model height and product length x width x height, and instruct the image model to strictly follow those measurements.
- Include concrete instructions to study the attached product images and preserve the exact product appearance and construction without inventing or changing its shape or structure.
- Include concrete instructions for coherent perspective between the model, product, body contact points, lens angle, shadows, and scene depth.
- Include concrete instructions forbidding poster-like added typography or graphic text overlays; naturally occurring scene text or real product text is allowed.
- The following guardrails must be reflected in every returned prompt:
{IMAGE_PROMPT_GUARDRAILS}
- Return only a JSON array of exactly {count} strings.
""".strip()
    prompts = call_chat_for_json(
        config,
        prompt,
        lambda value: validate_prompt_list(value, count),
        image_files=[product.front_image, model.image_path],
        logger=logger,
        label=f"第4步 生成{count}个英文生图提示词",
    )
    logger.write_json(f"第4步 生成{count}个英文生图提示词 - 解析结果", prompts)
    return prompts


def build_dimension_reference(product: ProductOption, model: ModelOption) -> str:
    product_description = read_text(product.description_path)
    model_description = read_text(model.description_path)
    product_dimensions = extract_product_dimensions(product.product, product_description)
    model_height = extract_model_height(model_description)
    if not model_height:
        raise RuntimeError(f"{model.name} 的模特描述缺少明确身高，请先补全 source/模特/{model.name}.md。")
    if not product_dimensions:
        raise RuntimeError(
            f"{product.product} 的产品描述缺少明确长宽高，请先补全产品描述 md。"
        )

    lines = [
        f"- Model height: {model_height}."
    ]
    lines.append(f"- Product length x width x height: {product_dimensions}.")
    return "\n".join(lines)


def extract_model_height(description: str) -> str | None:
    match = re.search(r"\bheight\s+([0-9]+(?:\.[0-9]+)?\s*cm)\b", description, re.I)
    if match:
        return match.group(1).strip()
    match = re.search(r"身高\s*([0-9]+(?:\.[0-9]+)?\s*(?:cm|厘米|米))", description, re.I)
    if match:
        return match.group(1).strip()
    return None


def extract_product_dimensions(product_name: str, description: str) -> str | None:
    size_match = re.search(r"\b(\d+)\s*Inch\b", product_name, re.I)
    if size_match:
        size = re.escape(size_match.group(1))
        match = re.search(
            rf"Local\s+{size}\s+Inch product folder represents.*?measures\s+(.+?)(?:\.\s|$)",
            description,
            re.I | re.S,
        )
        if match:
            return normalize_space(match.group(1))

    match = re.search(r"\bSize\s+(.+?)(?:\.\s|$)", description, re.I | re.S)
    if match:
        return normalize_space(match.group(1))

    match = re.search(
        r"measures\s+([0-9].+?)(?:\.\s|$)",
        description,
        re.I | re.S,
    )
    if match:
        return normalize_space(match.group(1))
    return None


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def with_image_prompt_guardrails(prompt: str, dimension_reference: str) -> str:
    sections = [prompt.strip()]
    if dimension_reference not in prompt:
        sections.append(f"Required dimension reference:\n{dimension_reference}")
    if IMAGE_PROMPT_GUARDRAILS not in prompt:
        sections.append(IMAGE_PROMPT_GUARDRAILS)
    return "\n\n".join(sections)


def call_chat_for_json(
    config: ChatConfig,
    prompt: str,
    validator: Any,
    image_files: list[Path] | None = None,
    logger: RunLogger | None = None,
    label: str = "chatpy JSON 请求",
) -> Any:
    current_prompt = prompt
    last_reply = ""
    last_reason = ""
    for attempt in range(1, MAX_CHAT_ATTEMPTS + 1):
        attempt_label = f"{label} - 第{attempt}次" if attempt > 1 else label
        last_reply = call_chat(
            config,
            current_prompt,
            image_files,
            logger=logger,
            label=attempt_label,
        )
        data = parse_json(last_reply)
        valid, result, reason = validator(data)
        if logger:
            logger.write_json(f"{label} - 第{attempt}次解析结果", data)
        if valid:
            return result

        last_reason = reason
        if logger:
            logger.write(f"{label} - 第{attempt}次校验失败", reason)
        current_prompt = build_retry_prompt(prompt, last_reply, reason)

    raise RuntimeError(
        f"{label} 连续 {MAX_CHAT_ATTEMPTS} 次没有返回合规结果：{last_reason}\n最后回复：{last_reply}"
    )


def build_retry_prompt(original_prompt: str, last_reply: str, reason: str) -> str:
    return f"""
{original_prompt}

上一次回复不符合要求，原因：
{reason}

上一次回复：
{last_reply}

请重新返回。必须只输出最终 JSON，本次不要输出分析、解释、Markdown 代码块或 <think> 内容。
""".strip()


def parse_json(text: str) -> Any:
    stripped = strip_model_thinking(text).strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    for candidate in iter_json_candidates(stripped):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None


def strip_model_thinking(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S | re.I)
    end_tag = "</think>"
    if end_tag in text:
        text = text.rsplit(end_tag, 1)[-1]
    return text.strip()


def iter_json_candidates(text: str) -> list[str]:
    candidates: list[str] = []
    fenced_matches = re.findall(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.S | re.I)
    candidates.extend(match.strip() for match in fenced_matches)

    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char not in "{[":
            continue
        try:
            _, end = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        candidates.append(text[index : index + end])

    candidates.sort(key=len, reverse=True)
    return candidates


def parse_prompt_list(reply: str) -> list[str]:
    data = parse_json(reply)
    if isinstance(data, list):
        return [item.strip() for item in data if isinstance(item, str) and item.strip()]
    if isinstance(data, dict) and isinstance(data.get("prompts"), list):
        return [
            item.strip()
            for item in data["prompts"]
            if isinstance(item, str) and item.strip()
        ]

    prompts: list[str] = []
    for line in reply.splitlines():
        line = re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", line).strip()
        if line:
            prompts.append(line.strip("\"'"))
    return prompts


def validate_product_match(
    data: Any,
    products: list[ProductOption],
) -> tuple[bool, dict[str, Any] | None, str]:
    if not isinstance(data, dict):
        return False, None, "返回内容不是 JSON 对象。"
    if not isinstance(data.get("matched"), bool):
        return False, None, "JSON 中缺少布尔字段 matched。"
    if not data["matched"]:
        return True, data, ""
    product_name = data.get("product")
    color_name = data.get("color")
    if not isinstance(product_name, str) or not isinstance(color_name, str):
        return False, None, "matched=true 时 product 和 color 必须是字符串。"
    if find_product(products, product_name, color_name) is None:
        return False, None, "product/color 没有完全匹配目录中的真实选项。"
    return True, data, ""


def validate_model_match(
    data: Any,
    models: list[ModelOption],
) -> tuple[bool, dict[str, Any] | None, str]:
    if not isinstance(data, dict):
        return False, None, "返回内容不是 JSON 对象。"
    if not isinstance(data.get("matched"), bool):
        return False, None, "JSON 中缺少布尔字段 matched。"
    if not data["matched"]:
        return True, data, ""
    model_name = data.get("model")
    if not isinstance(model_name, str):
        return False, None, "matched=true 时 model 必须是字符串。"
    if find_model(models, model_name) is None:
        return False, None, "model 没有完全匹配目录中的真实模特名。"
    return True, data, ""


def validate_prompt_list(data: Any, count: int) -> tuple[bool, list[str] | None, str]:
    prompts: list[str] = []
    if isinstance(data, list):
        prompts = [item.strip() for item in data if isinstance(item, str) and item.strip()]
    elif isinstance(data, dict) and isinstance(data.get("prompts"), list):
        prompts = [
            item.strip()
            for item in data["prompts"]
            if isinstance(item, str) and item.strip()
        ]
    else:
        return False, None, "返回内容不是 JSON 数组，也不是包含 prompts 数组的 JSON 对象。"

    if len(prompts) != count:
        return False, None, f"需要正好 {count} 条提示词，实际解析到 {len(prompts)} 条。"
    return True, prompts, ""


def find_product(
    products: list[ProductOption],
    product_name: str,
    color_name: str,
) -> ProductOption | None:
    for option in products:
        if option.product == product_name and option.color == color_name:
            return option
    return None


def find_model(models: list[ModelOption], name: str) -> ModelOption | None:
    for model in models:
        if model.name == name:
            return model
    return None


def product_log_data(product: ProductOption | None) -> dict[str, Any] | None:
    if product is None:
        return None
    return {
        "product": product.product,
        "color": product.color,
        "color_path": str(product.color_path),
        "front_image": str(product.front_image),
        "images": [str(path) for path in product.images],
        "description_path": str(product.description_path) if product.description_path else "",
    }


def model_log_data(model: ModelOption | None) -> dict[str, str] | None:
    if model is None:
        return None
    return {
        "name": model.name,
        "image_path": str(model.image_path),
        "description_path": str(model.description_path) if model.description_path else "",
    }


def choose_product(products: list[ProductOption]) -> ProductOption:
    product_names = sorted({option.product for option in products})
    product_name = choose_from_list("请选择产品", product_names)
    color_names = [option.color for option in products if option.product == product_name]
    color_name = choose_from_list(f"请选择 {product_name} 的颜色", color_names)
    product = find_product(products, product_name, color_name)
    if product is None:
        raise RuntimeError("选择的产品和颜色不存在。")
    return product


def choose_model(models: list[ModelOption]) -> ModelOption:
    name = choose_from_list("请选择模特", [model.name for model in models])
    model = find_model(models, name)
    if model is None:
        raise RuntimeError("选择的模特不存在。")
    return model


def choose_from_list(title: str, options: list[str]) -> str:
    print(f"\n{title}:")
    for index, option in enumerate(options, start=1):
        print(f"{index}. {option}")

    while True:
        raw = input("输入序号：").strip()
        if raw.isdigit():
            index = int(raw)
            if 1 <= index <= len(options):
                return options[index - 1]
        print("请输入列表中的有效序号。")


def read_text(path: Path | None) -> str:
    if path is None:
        return ""
    return path.read_text(encoding="utf-8").strip()


def generate_one_image(
    index: int,
    prompt: str,
    product: ProductOption,
    model: ModelOption,
    output_dir: Path,
    args: argparse.Namespace,
    config: ImageConfig,
    logger: RunLogger,
) -> list[Path]:
    image_inputs = [model.image_path, *product.images]
    if len(image_inputs) > MAX_IMAGE_INPUTS:
        raise RuntimeError(
            f"{product.product} / {product.color} 共有 {len(product.images)} 张产品图，"
            f"加上 1 张模特图超过接口最多 {MAX_IMAGE_INPUTS} 张参考图的限制。"
        )

    dimension_reference = build_dimension_reference(product, model)
    guarded_prompt = with_image_prompt_guardrails(prompt, dimension_reference)
    request_args = argparse.Namespace(
        prompt=guarded_prompt,
        size=args.size,
        resolution=args.resolution,
        n=1,
        image_urls=None,
        image_files=[str(path) for path in image_inputs],
        official_fallback=args.official_fallback,
        initial_delay=args.initial_delay,
        poll_interval=args.poll_interval,
        timeout=args.timeout,
        base_url=config.base_url,
        model=config.model,
    )
    logger.write_json(
        f"第5步 生图请求 {index} - 发送",
        {
            "model": config.model,
            "prompt": guarded_prompt,
            "size": args.size,
            "resolution": args.resolution,
            "n": 1,
            "official_fallback": args.official_fallback,
            "image_files": [str(path) for path in image_inputs],
        },
    )
    print(f"\n第 {index} 张图片任务提交中...", flush=True)
    task_id = image_client.submit_task(request_args, config.api_key)
    logger.write(f"第5步 生图请求 {index} - 任务已提交", f"task_id: {task_id}")
    print(f"第 {index} 张图片任务已提交: {task_id}", flush=True)
    task = image_client.poll_task(request_args, config.api_key, task_id)
    logger.write_json(f"第5步 生图请求 {index} - 任务完成响应", task)
    urls = image_client.collect_image_urls(task)
    logger.write_json(f"第5步 生图请求 {index} - 图片URL", urls)
    paths = image_client.download_images(urls, task_id, output_dir)
    logger.write_json(f"第5步 生图请求 {index} - 保存路径", [str(path) for path in paths])
    print(f"第 {index} 张图片已保存。", flush=True)
    return paths


def main() -> int:
    args = parse_args()
    logger = RunLogger()
    print(f"本次日志：{logger.path}")

    try:
        chat_config, image_config = load_configs()
        generation_count = load_generation_count()
        output_dir = image_client.OUTPUT_DIR / logger.timestamp
        logger.write_json(
            "配置",
            {
                "chat_model": chat_config.model,
                "chat_base_url": chat_config.base_url,
                "image_model": image_config.model,
                "image_base_url": image_config.base_url,
                "size": args.size,
                "resolution": args.resolution,
                "official_fallback": args.official_fallback,
                "timeout": args.timeout,
                "initial_delay": args.initial_delay,
                "poll_interval": args.poll_interval,
                "generation_count": generation_count,
                "default_generation_count": DEFAULT_IMAGE_GENERATION_COUNT,
                "generation_count_env": IMAGE_GENERATION_COUNT_ENV,
                "output_dir": str(output_dir),
            },
        )
        products = discover_products()
        models = discover_models()
        logger.write_json(
            "发现的产品目录",
            [product_log_data(product) for product in products],
        )
        logger.write_json(
            "发现的模特目录",
            [model_log_data(model) for model in models],
        )
        if not products:
            raise RuntimeError("source/产品 下没有可用的产品颜色目录。")
        if not models:
            raise RuntimeError("source/模特 下没有可用的模特图片。")

        user_idea = input("今天要生成什么图？\n> ").strip()
        if not user_idea:
            raise RuntimeError("没有输入生成需求。")
        logger.write("用户输入", user_idea)

        print("\n正在用 chatpy 分析产品、模特和参考图风格...")
        with ThreadPoolExecutor(max_workers=3) as executor:
            product_future = executor.submit(
                match_product_with_ai, user_idea, products, chat_config, logger
            )
            model_future = executor.submit(
                match_model_with_ai, user_idea, models, chat_config, logger
            )
            style_future = executor.submit(reverse_reference_style, chat_config, logger)

            product = product_future.result()
            model = model_future.result()
            style_prompt = style_future.result()

        if product is None:
            print("\n没有从你的描述里稳定匹配到产品和颜色。")
            product = choose_product(products)
            logger.write_json("手动选择产品和颜色", product_log_data(product))
        else:
            print(f"\n已匹配产品：{product.product} / {product.color}")

        if model is None:
            print("\n没有从你的描述里稳定匹配到模特。")
            model = choose_model(models)
            logger.write_json("手动选择模特", model_log_data(model))
        else:
            print(f"已匹配模特：{model.name}")

        logger.write_json(
            "最终选择",
            {
                "product": product_log_data(product),
                "model": model_log_data(model),
                "style_prompt": style_prompt,
            },
        )

        print(f"\n正在生成 {generation_count} 个英文生图提示词...")
        prompts = generate_image_prompts(
            user_idea,
            product,
            model,
            style_prompt,
            generation_count,
            chat_config,
            logger,
        )
        print(f"{len(prompts)} 个提示词已生成，详情见日志：{logger.path}")

        output_dir.mkdir(parents=True, exist_ok=True)
        print(f"\n正在并行提交 {len(prompts)} 个生图请求...")
        print(f"本次图片会保存到：{output_dir}")
        generated_paths: list[Path] = []
        with ThreadPoolExecutor(max_workers=len(prompts)) as executor:
            futures = [
                executor.submit(
                    generate_one_image,
                    index,
                    prompt,
                    product,
                    model,
                    output_dir,
                    args,
                    image_config,
                    logger,
                )
                for index, prompt in enumerate(prompts, start=1)
            ]
            for future in as_completed(futures):
                generated_paths.extend(future.result())

    except (RuntimeError, chat_client.ApiError, image_client.ApiError, TimeoutError) as exc:
        logger.write("运行失败", str(exc))
        print(f"错误: {exc}", file=sys.stderr)
        print(f"详细日志：{logger.path}", file=sys.stderr)
        return 1

    logger.write_json("全部完成，图片已保存", [str(path) for path in generated_paths])
    print("\n全部完成，图片已保存：")
    for path in generated_paths:
        print(path)
    print(f"详细日志：{logger.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

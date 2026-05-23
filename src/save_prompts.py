from __future__ import annotations

import argparse
from pathlib import Path


PROMPT_TYPES = {
    "reverse": "reverse",
    "reverse-prompt": "reverse",
    "反推词": "reverse",
    "反推提示词": "reverse",
    "image": "image",
    "image-prompt": "image",
    "生图词": "image",
    "生图提示词": "image",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="按类型保存反推提示词或生图提示词到 prompts 目录。"
    )
    parser.add_argument(
        "--run-dir",
        required=True,
        help="本次生图输出目录，例如 output/20260523-184941",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("prompts"),
        help="提示词保存目录，默认 prompts",
    )
    parser.add_argument(
        "prompt_type",
        choices=sorted(PROMPT_TYPES),
        help="提示词类型：reverse/反推词 或 image/生图词",
    )
    parser.add_argument(
        "prompts",
        nargs="+",
        help="提示词内容。image 类型可传多条；单个参数里的多行也会拆成多条。",
    )
    return parser.parse_args()


def compact_line(value: str) -> str:
    return " ".join(value.split())


def normalize_prompts(values: list[str]) -> list[str]:
    prompts: list[str] = []
    for value in values:
        prompts.extend(line for line in value.splitlines() if line.strip())
    return [compact_line(prompt) for prompt in prompts]


def output_path(run_dir: str, output_root: Path) -> Path:
    run_name = Path(run_dir).name
    return output_root / f"{run_name}.txt"


def write_reverse(path: Path, prompts: list[str]) -> None:
    if len(prompts) != 1:
        raise SystemExit("反推词类型只接受 1 条提示词")
    path.write_text(prompts[0] + "\n", encoding="utf-8")


def append_image_prompts(path: Path, prompts: list[str]) -> None:
    if not path.exists():
        raise SystemExit("请先写入反推词，再写入生图提示词")

    existing = path.read_text(encoding="utf-8").rstrip("\n")
    content = existing + "\n\n" + "\n".join(prompts) + "\n"
    path.write_text(content, encoding="utf-8")


def main() -> None:
    args = parse_args()
    prompt_type = PROMPT_TYPES[args.prompt_type]
    prompts = normalize_prompts(args.prompts)

    if not prompts:
        raise SystemExit("缺少提示词内容")

    args.output_root.mkdir(parents=True, exist_ok=True)
    path = output_path(args.run_dir, args.output_root)

    if prompt_type == "reverse":
        write_reverse(path, prompts)
    else:
        append_image_prompts(path, prompts)

    print(path)


if __name__ == "__main__":
    main()

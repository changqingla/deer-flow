from typing import Literal

from langchain.tools import tool


@tool("ask_clarification", parse_docstring=True, return_direct=True)
def ask_clarification_tool(
    question: str,
    clarification_type: Literal[
        "missing_info",
        "ambiguous_requirement",
        "approach_choice",
        "risk_confirmation",
        "suggestion",
    ],
    context: str | None = None,
    options: list[str] | None = None,
) -> str:
    """
    当遇到以下情况，无法在没有用户输入的前提下继续执行时，请使用此工具：

    - **信息缺失**：未提供必要细节（如文件路径、URL、具体约束）
    - **需求歧义**：同一需求存在多种合理解读
    - **方案选择**：存在多种可行方案，需要用户偏好
    - **高风险操作**：破坏性动作需要明确确认（如删文件、改生产配置）
    - **建议确认**：你有推荐方案，但需用户同意后再继续

    执行会被中断，并将问题展示给用户。
    请等待用户回复后再继续。

    ask_clarification 适用场景：
    - 需要用户请求中未提供的信息
    - 需求可被多种方式解释
    - 存在多种同样可行的实现路径
    - 即将执行潜在危险操作
    - 有建议但需要用户确认

    最佳实践：
    - 一次只问一个澄清问题，保持清晰
    - 问题应具体明确
    - 需要澄清时不要自行假设
    - 高风险操作必须先确认
    - 调用该工具后执行会自动中断

    参数：
        question: 向用户提出的澄清问题。应具体且清晰。
        clarification_type: 澄清类型（missing_info、ambiguous_requirement、approach_choice、risk_confirmation、suggestion）。
        context: 可选上下文，说明为何需要澄清，帮助用户理解当前情境。
        options: 可选候选项（适用于 approach_choice 或 suggestion），便于用户直接选择。
    """
    # 这里是占位实现
    # 实际逻辑由 ClarificationMiddleware 接管：拦截该工具调用，
    # 中断执行并向用户展示澄清问题
    return "Clarification request processed by middleware"

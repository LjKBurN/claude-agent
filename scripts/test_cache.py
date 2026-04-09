"""测试 Anthropic API 缓存命中。"""

import os
from anthropic import Anthropic

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# 生成足够长的系统提示（需要 >= 1024 tokens）
system_prompt = """You are a helpful assistant with access to various tools.

## Tool Usage Guidelines

When using tools, follow these best practices:

1. **Always validate inputs before calling tools**
   - Check that required parameters are present
   - Validate parameter types and formats
   - Handle edge cases gracefully

2. **Handle errors gracefully**
   - If a tool fails, analyze the error message
   - Try alternative approaches if possible
   - Report issues clearly to the user

3. **Provide clear explanations of what you're doing**
   - Explain which tool you're using and why
   - Describe the expected outcome
   - Share relevant results with the user

4. **Optimize tool usage**
   - Batch related operations when possible
   - Avoid redundant calls
   - Cache results when appropriate

## Response Format

When responding to users:

- Be concise and helpful
- Use markdown for formatting
- Include code examples when relevant
- Break down complex tasks into steps

## Security Considerations

- Never expose sensitive information
- Validate all user inputs
- Use caution with file operations
- Follow principle of least privilege

## Best Practices for Code Generation

- Write clean, readable code
- Include appropriate error handling
- Add comments for complex logic
- Follow language-specific conventions
- Consider edge cases and boundary conditions

## Communication Style

- Be direct and efficient
- Avoid unnecessary verbosity
- Use examples to clarify concepts
- Adapt to user's technical level
""" * 5  # 扩展到足够长

# 生成足够多的工具定义
tools = []
for i in range(10):
    tools.extend([
        {
            "name": f"tool_{i}_read",
            "description": f"Read data from source {i}. This tool accesses the data source numbered {i} and retrieves information based on the provided query parameters.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The query string to search for"},
                    "limit": {"type": "integer", "description": "Maximum number of results"},
                    "offset": {"type": "integer", "description": "Offset for pagination"},
                },
                "required": ["query"]
            }
        },
        {
            "name": f"tool_{i}_write",
            "description": f"Write data to destination {i}. This tool writes the provided data to the destination numbered {i}.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "data": {"type": "string", "description": "The data to write"},
                    "append": {"type": "boolean", "description": "Whether to append or overwrite"},
                },
                "required": ["data"]
            }
        }
    ])

# 在最后一个工具添加 cache_control
tools[-1]["cache_control"] = {"type": "ephemeral"}

def test_cache():
    """测试缓存命中情况。"""
    # 生成足够长的消息历史
    messages = []
    for i in range(20):
        messages.append({
            "role": "user",
            "content": f"Message {i}: This is a test message with some content to increase token count."
        })
        messages.append({
            "role": "assistant",
            "content": f"Response {i}: I understand your request and will help you with that."
        })

    # 在最后一条消息添加 cache_control
    messages[-1]["cache_control"] = {"type": "ephemeral"}

    # 第一次请求 - 写入缓存
    print("=== 第一次请求 (写入缓存) ===")
    response1 = client.messages.create(
        model="claude-sonnet-4-6-20250514",
        max_tokens=100,
        system=[
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"}
            }
        ],
        tools=tools,
        messages=messages,
    )

    usage1 = response1.usage
    print(f"Input tokens: {usage1.input_tokens}")
    print(f"Output tokens: {usage1.output_tokens}")
    print(f"Cache creation: {getattr(usage1, 'cache_creation_input_tokens', 0)} tokens")
    print(f"Cache read: {getattr(usage1, 'cache_read_input_tokens', 0)} tokens")

    # 第二次请求 - 应该命中缓存（相同的消息前缀）
    print("\n=== 第二次请求 (应该命中缓存) ===")

    # 添加一条新消息
    new_messages = messages.copy()
    new_messages.append({
        "role": "user",
        "content": "What tools do you have?"
    })

    response2 = client.messages.create(
        model="claude-sonnet-4-6-20250514",
        max_tokens=100,
        system=[
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"}
            }
        ],
        tools=tools,
        messages=new_messages,
    )

    usage2 = response2.usage
    print(f"Input tokens: {usage2.input_tokens}")
    print(f"Output tokens: {usage2.output_tokens}")
    print(f"Cache creation: {getattr(usage2, 'cache_creation_input_tokens', 0)} tokens")
    print(f"Cache read: {getattr(usage2, 'cache_read_input_tokens', 0)} tokens")

    # 计算节省
    cache_read = getattr(usage2, 'cache_read_input_tokens', 0) or 0
    cache_creation = getattr(usage2, 'cache_creation_input_tokens', 0) or 0

    if cache_read > 0:
        saved_cost = (cache_read / 1_000_000) * (3.00 - 0.30)
        print(f"\n=== 缓存命中! ===")
        print(f"缓存读取: {cache_read} tokens")
        print(f"节省费用: ${saved_cost:.6f}")
    elif cache_creation > 0:
        print(f"\n=== 缓存已创建 ===")
        print(f"缓存写入: {cache_creation} tokens")
    else:
        print("\n=== 缓存未命中 ===")

if __name__ == "__main__":
    test_cache()

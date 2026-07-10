## 9. AI Service Addendum

> Included when the service builds or operates AI/LLM systems.

### Intended use case

[What the AI system is for and the decisions or tasks it supports.]

### Approved users

- [Who is permitted to use the system]

### Prohibited or restricted uses

- Fully automated high-impact decisions without human oversight
- Processing unlawful or unauthorised data
- Use outside the approved context
- [Service-specific restriction]

### Model and system approach

- **Model provider:** [OpenAI / Anthropic / Gemini / Other]
- **Model or model class:** [Model]
- **Architecture:** [Prompting / RAG / Agent / Classification / Recommendation / Custom model]
- **Grounding sources:** [Data sources]
- **Fallback behaviour:** [What happens on low confidence or failure]

### Human oversight

- Human review is required when [decision type], for high-impact actions, and for low-confidence outputs.

### Evaluation criteria

| Evaluation area | Method | Target |
| --- | --- | --- |
| Accuracy | [Method] | [Target] |
| Groundedness | [Method] | [Target] |
| Relevance | [Method] | [Target] |
| Safety | [Method] | [Target] |
| Response time | [Method] | [Target] |
| Cost per interaction | [Method] | [Target] |

### Known risks

- Hallucination, incorrect retrieval, prompt injection, data exposure, bias, and cost volatility.

### Controls

- Input validation, output review, access control, logging, and rate limits.

### Monitoring

- Quality, cost, latency, and error monitoring with alerting.

### Data use

- [ ] Confirm provider data retention terms
- [ ] Confirm whether inputs are used for training
- [ ] Confirm permission to process any personal data
- [ ] Confirm regions and vendors involved

### AI limitations

AI outputs may be incomplete or incorrect and must not be treated as professional advice. The system supports human decision-making; it does not replace accountable human judgement.

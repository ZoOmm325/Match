"use client";

import { useState } from "react";
import JdInput from "@/components/JdInput";
import MatchButton from "@/components/MatchButton";
import MatchResult from "@/components/MatchResult";
import { useToast } from "@/components/ui/Toast";
import { ApiError, type MatchResponseData, submitJD } from "@/lib/api";

const MIN_JD_LENGTH = 20;
const MAX_JD_LENGTH = 20_000;

const EXAMPLE_JD = `岗位名称：AI 后端工程师

岗位职责：
1. 负责智能应用后端服务与 REST API 的设计、开发和维护；
2. 参与大语言模型、自然语言处理相关功能的工程落地；
3. 持续优化服务性能、稳定性和部署流程。

任职要求：
1. 熟练掌握 Python，具有 FastAPI 或 Django 项目经验；
2. 熟悉 PostgreSQL、Redis、Docker 和 Linux；
3. 了解机器学习、NLP 或大语言模型应用开发；
4. 具备良好的沟通能力和团队协作意识。`;

export default function HomePage() {
  const { showToast } = useToast();
  const [jdText, setJdText] = useState("");
  const [validationError, setValidationError] = useState("");
  const [requestError, setRequestError] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<MatchResponseData | null>(null);

  const handleTextChange = (value: string) => {
    setJdText(value);
    if (validationError) {
      setValidationError("");
    }
    if (requestError) {
      setRequestError("");
    }
  };

  const handleUseExample = () => {
    setJdText(EXAMPLE_JD);
    setValidationError("");
    setRequestError("");
    setResult(null);
  };

  const handleMatch = async () => {
    const normalized = jdText.trim();
    if (!normalized) {
      setValidationError("请输入岗位描述后再开始匹配。");
      return;
    }
    if (normalized.length < MIN_JD_LENGTH) {
      setValidationError(`岗位描述至少需要 ${MIN_JD_LENGTH} 个字符。`);
      return;
    }
    if (normalized.length > MAX_JD_LENGTH) {
      setValidationError(`岗位描述不能超过 ${MAX_JD_LENGTH.toLocaleString()} 个字符。`);
      return;
    }

    setLoading(true);
    setValidationError("");
    setRequestError("");
    setResult(null);
    try {
      const matchResult = await submitJD(normalized, {
        major_top_n: 5,
        generate_reasons: false,
      });
      setResult(matchResult);
      showToast({
        title: "匹配完成",
        description: `已生成 ${matchResult.recommendations.length} 个专业建议。`,
        variant: "success",
      });
    } catch (error) {
      const message = error instanceof ApiError ? error.message : "匹配请求失败，请稍后重试。";
      setRequestError(message);
      showToast({
        title: "匹配失败",
        description: message,
        variant: "error",
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 lg:px-8 lg:py-10">
      <header className="mb-7 max-w-3xl">
        <p className="text-sm font-semibold text-sky-700">岗位能力与专业匹配</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-normal text-slate-950 sm:text-4xl">
          从招聘 JD 找到最相关的大学专业
        </h1>
        <p className="mt-3 text-base leading-7 text-slate-600">
          系统会抽取岗位所需技能，结合技能覆盖率和专业培养方向生成推荐结果。
        </p>
      </header>

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1.15fr)_minmax(340px,0.85fr)]">
        <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm sm:p-6 lg:sticky lg:top-6">
          <JdInput
            value={jdText}
            maxLength={MAX_JD_LENGTH}
            error={validationError}
            disabled={loading}
            onChange={handleTextChange}
            onUseExample={handleUseExample}
          />

          {requestError ? (
            <div
              role="alert"
              className="mt-4 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
            >
              {requestError}
            </div>
          ) : null}

          <div className="mt-5 flex flex-col gap-3 border-t border-slate-200 pt-5 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-slate-500">最多返回 5 个推荐专业，通常需要数秒完成。</p>
            <MatchButton loading={loading} disabled={!jdText.trim()} onClick={handleMatch} />
          </div>
        </div>

        <MatchResult loading={loading} result={result} />
      </div>
    </section>
  );
}

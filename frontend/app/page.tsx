"use client";

import { useState } from "react";
import JdInput from "@/components/JdInput";
import MatchButton from "@/components/MatchButton";
import MatchResult from "@/components/MatchResult";
import { useToast } from "@/components/ui/Toast";
import { ApiError, fetchPublicJd, type MatchResponseData, submitJD } from "@/lib/api";

const MIN_JD_LENGTH = 20;
const MAX_JD_LENGTH = 20_000;

const EXAMPLE_JOBS = [
  {
    id: "algorithm-engineer",
    title: "算法工程师",
    summary: "机器学习、深度学习、模型训练与评估",
    jd: `岗位名称：算法工程师
岗位职责：
1. 负责推荐、搜索或风控场景中的机器学习算法建模、训练和效果评估；
2. 参与特征工程、模型调参、离线实验和线上 A/B 测试，持续优化核心业务指标；
3. 与后端、数据和产品团队协作，推动算法方案在生产环境稳定落地。

任职要求：
1. 熟悉 Python，掌握 NumPy、Pandas、scikit-learn、PyTorch 或 TensorFlow；
2. 理解常见机器学习、深度学习、推荐系统或自然语言处理算法；
3. 具备数据分析、实验设计和模型评估经验，熟悉 SQL；
4. 有良好的工程实现能力和团队协作意识。`,
  },
  {
    id: "backend-engineer",
    title: "后端工程师",
    summary: "Python、FastAPI、数据库与服务稳定性",
    jd: `岗位名称：后端工程师
岗位职责：
1. 负责业务后端服务、REST API 和异步任务的设计、开发与维护；
2. 参与数据库表结构设计、性能优化、日志监控和故障排查；
3. 与前端、算法和运维团队协作，保障服务稳定交付。

任职要求：
1. 熟悉 Python，具备 FastAPI、Django 或 Flask 项目经验；
2. 熟悉 PostgreSQL、Redis、Linux、Docker 和常见 Web 服务架构；
3. 理解接口设计、权限校验、异常处理、单元测试和 CI/CD 流程；
4. 具备清晰的技术表达能力和工程质量意识。`,
  },
  {
    id: "financial-analyst",
    title: "财务分析师",
    summary: "预算管理、经营分析、财务模型与报表",
    jd: `岗位名称：财务分析师
岗位职责：
1. 负责月度经营分析、预算执行跟踪、成本费用拆解和管理报表输出；
2. 搭建收入、毛利、现金流等财务模型，为业务决策提供量化依据；
3. 与业务、采购和财务共享团队协作，识别经营风险并提出改善建议。

任职要求：
1. 熟悉会计、财务管理和管理会计基础，能独立阅读财务报表；
2. 熟练使用 Excel，了解 Power BI、SQL 或 Python 数据处理优先；
3. 具备预算管理、成本分析、经营分析或审计相关经验；
4. 逻辑严谨，对数据准确性和合规性保持敏感。`,
  },
  {
    id: "mechanical-engineer",
    title: "机械设计工程师",
    summary: "机械结构、CAD、工艺评审与量产支持",
    jd: `岗位名称：机械设计工程师
岗位职责：
1. 负责产品机械结构设计、零部件选型、工程图绘制和 BOM 维护；
2. 参与样机试制、工艺评审、可靠性验证和量产问题分析；
3. 与电气、供应链、质量和生产团队协作，推动产品按期交付。

任职要求：
1. 熟悉机械原理、材料力学、公差配合和常见加工工艺；
2. 熟练使用 SolidWorks、Creo、AutoCAD 或同类三维建模软件；
3. 了解钣金、注塑、机加工、装配和可靠性测试流程；
4. 具备问题分析能力、文档规范意识和跨部门沟通能力。`,
  },
  {
    id: "clinical-research-associate",
    title: "临床研究专员",
    summary: "临床试验、GCP、伦理资料与项目协调",
    jd: `岗位名称：临床研究专员
岗位职责：
1. 协助临床试验项目启动、伦理资料准备、研究中心沟通和进度跟踪；
2. 维护试验文档，跟进受试者入组、数据录入、问题反馈和质量核查；
3. 与研究者、申办方、CRO 和内部医学团队保持沟通，保障项目合规推进。

任职要求：
1. 具备临床医学、药学、护理学、生物医学或公共卫生相关知识；
2. 熟悉 GCP、临床试验基本流程和医学文档管理要求；
3. 具备细致的执行能力、沟通协调能力和风险意识；
4. 能接受一定频率的研究中心现场沟通和项目节点压力。`,
  },
  {
    id: "english-teacher",
    title: "英语教师",
    summary: "课程设计、课堂教学、学情分析与家校沟通",
    jd: `岗位名称：英语教师
岗位职责：
1. 根据学生水平设计教学计划，完成听说读写课程授课和课后反馈；
2. 跟踪学生学习数据，进行阶段测评、错题分析和个性化辅导；
3. 参与教研、公开课、教材优化和家校沟通，提升教学效果。

任职要求：
1. 英语、教育学、翻译或相关专业背景，英语表达流利；
2. 熟悉语言教学法、课堂管理、学习评估和课程设计；
3. 具备教师资格证、雅思托福教学经验或海外学习经历优先；
4. 有耐心、责任心和良好的沟通表达能力。`,
  },
  {
    id: "new-media-operator",
    title: "新媒体运营",
    summary: "内容策划、短视频、社群增长与数据复盘",
    jd: `岗位名称：新媒体运营
岗位职责：
1. 负责公众号、视频号、小红书或抖音等平台的内容策划、发布和复盘；
2. 结合热点、用户画像和产品卖点，产出图文、短视频脚本和活动方案；
3. 跟踪阅读量、转化率、粉丝增长和互动数据，持续优化内容策略。

任职要求：
1. 具备新闻传播、广告、中文、市场营销或相关内容经验；
2. 熟悉内容选题、文案写作、短视频流程和基础图片视频编辑工具；
3. 理解用户运营、社群维护、活动策划和数据复盘方法；
4. 对热点敏感，表达清晰，能稳定输出高质量内容。`,
  },
  {
    id: "hr-specialist",
    title: "人力资源专员",
    summary: "招聘配置、员工关系、培训与组织支持",
    jd: `岗位名称：人力资源专员
岗位职责：
1. 负责岗位发布、简历筛选、面试协调、入离职办理和员工档案维护；
2. 支持培训组织、绩效流程、员工关系沟通和基础人事数据统计；
3. 与业务部门沟通用人需求，提升招聘效率和员工体验。

任职要求：
1. 了解人力资源管理、劳动法规、招聘流程和员工关系基础知识；
2. 熟练使用 Office，具备数据整理、表格统计和流程跟进能力；
3. 具备良好的沟通协调能力、保密意识和服务意识；
4. 有校园招聘、企业文化活动或培训项目经验优先。`,
  },
];

export default function HomePage() {
  const { showToast } = useToast();
  const [jdText, setJdText] = useState("");
  const [validationError, setValidationError] = useState("");
  const [requestError, setRequestError] = useState("");
  const [loading, setLoading] = useState(false);
  const [fetchingJd, setFetchingJd] = useState(false);
  const [result, setResult] = useState<MatchResponseData | null>(null);
  const [selectedExampleId, setSelectedExampleId] = useState<string | null>(null);

  const handleTextChange = (value: string) => {
    setJdText(value);
    if (validationError) {
      setValidationError("");
    }
    if (requestError) {
      setRequestError("");
    }
  };

  const handleUseExample = (exampleId: string) => {
    const example = EXAMPLE_JOBS.find((item) => item.id === exampleId);
    if (!example) {
      return;
    }
    setJdText(example.jd);
    setSelectedExampleId(example.id);
    setValidationError("");
    setRequestError("");
    setResult(null);
  };

  const handleFetchPublicJd = async (keyword: string, sourceUrl?: string) => {
    const normalized = keyword.trim();
    if (normalized.length < 2) {
      throw new Error("请输入至少 2 个字符的岗位关键词。");
    }

    setFetchingJd(true);
    setValidationError("");
    setRequestError("");
    setResult(null);
    try {
      const fetched = await fetchPublicJd({
        keyword: normalized,
        source_url: sourceUrl?.trim() || undefined,
        max_results: 3,
      });
      setJdText(fetched.jd_text);
      setSelectedExampleId(null);
      showToast({
        title: "已获取公开 JD",
        description: fetched.source_domain ? `来源：${fetched.source_domain}` : "已填入文本框。",
        variant: "success",
      });
      return fetched;
    } catch (error) {
      const message =
        error instanceof ApiError || error instanceof Error
          ? error.message
          : "联网搜索 JD 失败，请稍后重试。";
      showToast({
        title: "联网搜索失败",
        description: message,
        variant: "error",
      });
      throw new Error(message);
    } finally {
      setFetchingJd(false);
    }
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
            fetchingJd={fetchingJd}
            examples={EXAMPLE_JOBS}
            selectedExampleId={selectedExampleId}
            onChange={handleTextChange}
            onUseExample={handleUseExample}
            onFetchPublicJd={handleFetchPublicJd}
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

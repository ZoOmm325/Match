import asyncio
from types import SimpleNamespace

import pytest

from backend.services.jd_service import ExtractedSkillResult, JdExtractionResult
from backend.services.matching import MajorMatcher, MajorMatchResult
from backend.services.vector_service import VectorSearchResult


class FakeVectorService:
    def __init__(self, results):
        self.results = results
        self.calls = []

    async def search_majors(self, query_embedding, *, top_k):
        self.calls.append({"query_embedding": query_embedding, "top_k": top_k})
        return self.results


class FakeJdService:
    def __init__(self, extraction):
        self.extraction = extraction
        self.calls = []

    async def extract_skills(self, jd_text):
        self.calls.append(jd_text)
        return self.extraction


def skill(name, category, embedding):
    return ExtractedSkillResult(
        name=name,
        normalized_name=name,
        category=category,
        proficiency_required="intermediate",
        embedding=embedding,
    )


def major_candidate(
    name, score, *, major_id=1, code="080901", category="工学", description="", curriculum=None
):
    item = SimpleNamespace(
        id=major_id,
        name=name,
        code=code,
        category=category,
        description=description,
        curriculum=curriculum or {},
    )
    return VectorSearchResult(
        item=item,
        similarity_score=score,
        table="majors",
        id=major_id,
        name=name,
        category=category,
    )


def test_match_skills_to_majors_aggregates_vectors_and_scores_candidates():
    skills = [
        skill("Python", "programming_language", [1.0, 0.0]),
        skill("FastAPI", "framework", [0.0, 1.0]),
    ]
    vector_service = FakeVectorService(
        [
            major_candidate(
                "软件工程",
                0.8,
                major_id=1,
                curriculum={"core": ["Python", "FastAPI"]},
            ),
            major_candidate(
                "会计学", 0.9, major_id=2, category="管理学", description="financial reports"
            ),
        ]
    )
    matcher = MajorMatcher(
        vector_service=vector_service, similarity_weight=0.7, coverage_weight=0.3
    )

    results = asyncio.run(matcher.match_skills_to_majors(skills, top_n=2))

    assert vector_service.calls == [
        {"query_embedding": pytest.approx([0.70710678, 0.70710678]), "top_k": 6}
    ]
    assert [result.major_name for result in results] == ["软件工程", "会计学"]
    assert results[0] == MajorMatchResult(
        major_id=1,
        major_name="软件工程",
        major_code="080901",
        major_category="工学",
        similarity_score=0.8,
        coverage_score=1.0,
        final_score=0.86,
        matched_skills=["Python", "FastAPI"],
        missing_skills=[],
        match_details={
            "similarity_weight": 0.7,
            "coverage_weight": 0.3,
            "skill_count": 2,
            "matched_skill_count": 2,
        },
    )
    assert results[1].coverage_score == 0.0
    assert results[1].missing_skills == ["Python", "FastAPI"]


def test_match_skills_to_majors_limits_and_sorts_by_final_score():
    skills = [skill("Data Analysis", "data", [1.0, 0.0])]
    vector_service = FakeVectorService(
        [
            major_candidate("统计学", 0.7, major_id=1, category="理学"),
            major_candidate("金融学", 0.95, major_id=2, category="经济学"),
        ]
    )
    matcher = MajorMatcher(
        vector_service=vector_service, similarity_weight=0.5, coverage_weight=0.5
    )

    results = asyncio.run(matcher.match_skills_to_majors(skills, top_n=1, candidate_multiplier=4))

    assert [result.major_name for result in results] == ["金融学"]
    assert vector_service.calls[0]["top_k"] == 4


def test_match_jd_to_majors_uses_jd_service_extraction():
    extraction = JdExtractionResult(
        jd_id=1,
        skills=[skill("Machine Learning", "ai", [1.0, 0.0])],
    )
    jd_service = FakeJdService(extraction)
    vector_service = FakeVectorService([major_candidate("人工智能", 0.88, category="工学")])
    matcher = MajorMatcher(vector_service=vector_service, jd_service=jd_service)

    results = asyncio.run(matcher.match_jd_to_majors("Need ML engineer.", top_n=3))

    assert jd_service.calls == ["Need ML engineer."]
    assert results[0].major_name == "人工智能"
    assert results[0].matched_skills == ["Machine Learning"]
    assert results[0].missing_skills == []


def test_match_skills_to_majors_returns_empty_for_empty_skills():
    matcher = MajorMatcher(vector_service=FakeVectorService([]))

    assert asyncio.run(matcher.match_skills_to_majors([])) == []


def test_split_covered_skills_uses_word_boundaries_for_short_skill_names():
    matcher = MajorMatcher(vector_service=FakeVectorService([]))
    major = SimpleNamespace(
        name="Engineering Design",
        code="080000",
        category="other",
        description="Courses include C++ programming and statistics.",
        curriculum={"core": ["CAD modeling"]},
    )
    skills = [
        skill("C", "other", [1.0]),
        skill("CAD", "other", [1.0]),
    ]

    matched, missing = matcher._split_covered_skills(major, skills)

    assert matched == ["CAD"]
    assert missing == ["C"]


def test_split_covered_skills_ignores_incidental_description_mentions():
    matcher = MajorMatcher(vector_service=FakeVectorService([]))
    major = SimpleNamespace(
        name="Business Administration",
        code="120201",
        category="management",
        description="Graduates may collaborate with Python development teams.",
        curriculum={"core": ["Management", "Accounting"]},
    )

    matched, missing = matcher._split_covered_skills(
        major,
        [skill("Python", "programming_language", [1.0])],
    )

    assert matched == []
    assert missing == ["Python"]


def test_split_covered_skills_derives_database_skills_from_curriculum():
    matcher = MajorMatcher(vector_service=FakeVectorService([]))
    major = SimpleNamespace(
        name="软件工程",
        code="080902",
        category="工学",
        description="不依赖描述中的 PostgreSQL 字样做覆盖判断。",
        curriculum={"core": ["数据库系统", "软件需求工程", "软件测试技术"]},
    )
    skills = [
        skill("PostgreSQL", "database", [1.0]),
        skill("Database Design", "database", [1.0]),
        skill("Unit Testing", "testing", [1.0]),
        skill("Docker", "devops", [1.0]),
    ]

    matched, missing = matcher._split_covered_skills(major, skills)

    assert matched == ["PostgreSQL", "Database Design", "Unit Testing", "Docker"]
    assert missing == []


def test_split_covered_skills_derives_ai_skills_from_major_and_courses():
    matcher = MajorMatcher(vector_service=FakeVectorService([]))
    major = SimpleNamespace(
        name="人工智能",
        code="080717T",
        category="工学",
        description=None,
        curriculum={"core": ["深度学习", "自然语言处理"]},
    )
    skills = [
        skill("Machine Learning", "ai", [1.0]),
        skill("PyTorch", "ai", [1.0]),
        skill("NLP", "ai", [1.0]),
        skill("Kubernetes", "devops", [1.0]),
    ]

    matched, missing = matcher._split_covered_skills(major, skills)

    assert matched == ["Machine Learning", "PyTorch", "NLP"]
    assert missing == ["Kubernetes"]


def test_split_covered_skills_does_not_treat_security_testing_as_software_testing():
    matcher = MajorMatcher(vector_service=FakeVectorService([]))
    major = SimpleNamespace(
        name="信息安全",
        code="080904K",
        category="工学",
        description=None,
        curriculum={"practice": ["渗透测试实训", "安全攻防演练"]},
    )

    matched, missing = matcher._split_covered_skills(
        major,
        [
            skill("Cybersecurity", "domain_knowledge", [1.0]),
            skill("Selenium", "testing", [1.0]),
        ],
    )

    assert matched == ["Cybersecurity"]
    assert missing == ["Selenium"]


def test_split_covered_skills_adds_common_foundation_for_computer_majors():
    matcher = MajorMatcher(vector_service=FakeVectorService([]))
    major = SimpleNamespace(
        name="人工智能",
        code="080717T",
        category="工学",
        description=None,
        curriculum={"core": ["机器学习", "自然语言处理"]},
    )
    skills = [
        skill("Linux", "operating_system", [1.0]),
        skill("Docker", "devops", [1.0]),
        skill("CI/CD", "devops", [1.0]),
        skill("REST API", "backend", [1.0]),
        skill("FastAPI", "framework", [1.0]),
    ]

    matched, missing = matcher._split_covered_skills(major, skills)

    assert matched == ["Linux", "Docker", "CI/CD", "REST API"]
    assert missing == ["FastAPI"]


def test_split_covered_skills_covers_fastapi_only_for_software_or_backend_direction():
    matcher = MajorMatcher(vector_service=FakeVectorService([]))
    major = SimpleNamespace(
        name="软件工程",
        code="080902",
        category="工学",
        description=None,
        curriculum={"core": ["软件需求工程", "接口设计与后端开发"]},
    )

    matched, missing = matcher._split_covered_skills(
        major,
        [
            skill("FastAPI", "framework", [1.0]),
            skill("Spring Boot", "framework", [1.0]),
            skill("Docker", "devops", [1.0]),
        ],
    )

    assert matched == ["FastAPI", "Spring Boot", "Docker"]
    assert missing == []


def test_split_covered_skills_does_not_add_computer_foundation_to_business_major():
    matcher = MajorMatcher(vector_service=FakeVectorService([]))
    major = SimpleNamespace(
        name="工商管理",
        code="120201",
        category="管理学",
        description="数字化管理岗位可能协同软件团队。",
        curriculum={"core": ["管理学", "会计学", "市场营销"]},
    )

    matched, missing = matcher._split_covered_skills(
        major,
        [
            skill("Linux", "operating_system", [1.0]),
            skill("Docker", "devops", [1.0]),
            skill("CI/CD", "devops", [1.0]),
        ],
    )

    assert matched == []
    assert missing == ["Linux", "Docker", "CI/CD"]


def test_major_matcher_validates_inputs_and_dependencies():
    matcher = MajorMatcher(vector_service=FakeVectorService([]))

    with pytest.raises(ValueError, match="same dimension"):
        matcher._aggregate_embedding([[1.0, 2.0], [1.0]])

    with pytest.raises(ValueError, match="top_n"):
        asyncio.run(
            matcher.match_skills_to_majors(
                [skill("Python", "programming_language", [1.0])], top_n=0
            )
        )

    with pytest.raises(ValueError, match="candidate_multiplier"):
        asyncio.run(
            matcher.match_skills_to_majors(
                [skill("Python", "programming_language", [1.0])],
                candidate_multiplier=0,
            )
        )

    with pytest.raises(RuntimeError, match="vector_service"):
        asyncio.run(
            MajorMatcher().match_skills_to_majors([skill("Python", "programming_language", [1.0])])
        )

    with pytest.raises(RuntimeError, match="jd_service"):
        asyncio.run(matcher.match_jd_to_majors("Need Python."))

    with pytest.raises(ValueError, match="weights"):
        MajorMatcher(vector_service=FakeVectorService([]), similarity_weight=0, coverage_weight=0)


def test_matching_package_exports_major_matcher():
    import backend.services as services
    import backend.services.matching as matching

    assert "MajorMatcher" in matching.__all__
    assert "MajorMatchResult" in matching.__all__
    assert services.MajorMatcher is MajorMatcher

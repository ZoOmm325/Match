from backend.services.jd_skill_extractor import JdSkillExtractor


def test_extract_skills_from_chinese_jd():
    extractor = JdSkillExtractor()
    jd_text = (
        "我们招聘后端工程师，要求熟练掌握 Python、FastAPI、PostgreSQL，"
        "熟悉 Docker 和 Linux，有 RESTful API 接口开发经验，具备良好沟通协作能力。"
    )

    skills = extractor.extract(jd_text)
    names = {skill.name for skill in skills}

    assert {"Python", "FastAPI", "PostgreSQL", "Docker", "Linux", "REST API"}.issubset(names)
    assert len(skills) >= 6
    assert all(0 <= skill.confidence <= 1 for skill in skills)


def test_extract_deduplicates_aliases():
    extractor = JdSkillExtractor()
    jd_text = "需要熟悉 Next.js 和 nextjs，同时掌握 TypeScript 和 TS 工程化。"

    skills = extractor.extract(jd_text)
    names = [skill.name for skill in skills]

    assert names.count("Next.js") == 1
    assert names.count("TypeScript") == 1


def test_extract_infers_advanced_proficiency():
    extractor = JdSkillExtractor()
    jd_text = "候选人需要精通 Python，深入理解机器学习算法，并能独立完成模型训练。"

    skills = extractor.extract(jd_text)
    python_skill = next(skill for skill in skills if skill.name == "Python")

    assert python_skill.proficiency_required == "advanced"

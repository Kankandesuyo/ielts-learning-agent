let currentUserId = localStorage.getItem("ielts_user_id");
let currentKnowledgeQuestionId = null;
let readingExam = null;
let examTimerHandle = null;
let examSecondsLeft = 3600;
let selectedExamVocabulary = null;
let selectedExamRange = null;
let examVocabularyTimer = null;
let examVocabularyRequestId = 0;
let examVocabularyDragStart = null;

const $ = (id) => document.getElementById(id);

function setUser(id) {
  currentUserId = String(id);
  localStorage.setItem("ielts_user_id", currentUserId);
  $("currentUserId").textContent = currentUserId;
}

function requireUser() {
  if (!currentUserId) {
    throw new Error("请先创建用户画像。");
  }
  return Number(currentUserId);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || "请求失败");
  }
  return data;
}

async function withButtonLoading(button, label, task) {
  const originalText = button.textContent;
  button.disabled = true;
  button.classList.add("loading");
  button.textContent = label;
  try {
    return await task();
  } finally {
    button.disabled = false;
    button.classList.remove("loading");
    button.textContent = originalText;
  }
}

function showError(target, error) {
  const box = document.createElement("div");
  box.className = "error";
  box.textContent = error instanceof Error ? error.message : "请求失败";
  target.replaceChildren(box);
}

function showLoading(target, text = "处理中，请稍等...") {
  const box = document.createElement("div");
  box.className = "empty";
  box.textContent = text;
  target.replaceChildren(box);
}

async function refreshServiceStatus() {
  const target = $("serviceStatus");
  try {
    const data = await api("/health");
    target.textContent = data.status === "ok" ? "服务正常" : "服务异常";
    target.classList.toggle("ok", data.status === "ok");
    target.classList.toggle("bad", data.status !== "ok");
  } catch (_) {
    target.textContent = "服务未连接";
    target.classList.add("bad");
  }
}

const viewDefaults = {
  today: "profile",
  practice: "writing",
  library: "exam",
};

const legacyRoutes = {
  home: ["today", "profile"],
  profile: ["today", "profile"],
  supervisor: ["today", "supervisor"],
  plan: ["today", "plan"],
  writing: ["practice", "writing"],
  speaking: ["practice", "speaking"],
  reading: ["practice", "reading"],
  listening: ["practice", "listening"],
  vocabulary: ["practice", "vocabulary"],
  exam: ["library", "exam"],
  documents: ["library", "documents"],
  errors: ["library", "errors"],
};

function switchTool(toolName) {
  const targetTool = document.querySelector(`[data-tool="${toolName}"]`);
  if (!targetTool?.dataset?.toolGroup) return;
  const group = targetTool.dataset.toolGroup;

  document.querySelectorAll(`[data-tool-group="${group}"]`).forEach((tool) => {
    tool.hidden = tool.dataset.tool !== toolName;
  });
  document.querySelectorAll(`[data-tool-link]`).forEach((button) => {
    const linkedTool = document.querySelector(`[data-tool="${button.dataset.toolLink}"]`);
    button.classList.toggle("active", linkedTool?.dataset?.toolGroup === group && button.dataset.toolLink === toolName);
  });
}

function switchView(viewName, updateHash = true, toolName = null) {
  const route = legacyRoutes[viewName];
  const resolvedView = route ? route[0] : viewName;
  const resolvedTool = toolName || (route ? route[1] : null);
  const targetView = document.querySelector(`[data-view="${resolvedView}"]`);
  if (!targetView) {
    return;
  }

  document.querySelectorAll("[data-view]").forEach((view) => {
    view.hidden = view.dataset.view !== resolvedView;
  });

  document.querySelectorAll("[data-view-link]").forEach((link) => {
    link.classList.toggle("active", link.dataset.viewLink === resolvedView);
  });

  switchTool(resolvedTool || viewDefaults[resolvedView]);

  if (updateHash && window.location.hash !== `#${resolvedView}`) {
    window.history.pushState(null, "", `#${resolvedView}`);
  }
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "'": "&#39;",
    '"': "&quot;",
  })[character]);
}

function textWithBreaks(value) {
  return escapeHtml(value).replace(/\n/g, "<br />");
}

function item(title, body) {
  return `<div class="item"><strong>${escapeHtml(title)}</strong><p>${textWithBreaks(body)}</p></div>`;
}

function score(text) {
  return `<div class="score">${escapeHtml(text)}</div>`;
}

const resultLabels = {
  passage: "阅读材料",
  question_type: "题型",
  question: "题目",
  strategy: "解题策略",
  next_step: "下一步",
  scenario: "听力场景",
  transcript: "听力文本",
  audio_ready: "音频状态",
  future_audio_api: "音频能力",
  part: "口语部分",
  task_response: "任务回应",
  coherence_and_cohesion: "连贯与衔接",
  lexical_resource: "词汇资源",
  grammatical_range_and_accuracy: "语法多样性与准确性",
  "Task Response / Task Achievement": "任务回应 / 任务完成度",
  "Coherence and Cohesion": "连贯与衔接",
  "Lexical Resource": "词汇资源",
  "Grammatical Range and Accuracy": "语法多样性与准确性",
  reading_agent: "阅读 Agent",
  listening_agent: "听力 Agent",
  speaking_agent: "口语 Agent",
  writing_agent: "写作 Agent",
};

function resultLabel(key) {
  const readable = String(key).replaceAll("_", " ");
  return resultLabels[key] || readable.charAt(0).toUpperCase() + readable.slice(1);
}

function resultHeading(title, subtitle = "") {
  return `
    <header class="result-heading">
      <span>学习结果</span>
      <h4>${escapeHtml(title)}</h4>
      ${subtitle ? `<p>${escapeHtml(subtitle)}</p>` : ""}
    </header>
  `;
}

function featuredItem(label, body, variant = "source", meta = "") {
  return `
    <section class="featured-item featured-${escapeHtml(variant)}">
      <div class="featured-label">${escapeHtml(label)}</div>
      ${meta ? `<div class="featured-meta">${escapeHtml(meta)}</div>` : ""}
      <div class="featured-body">${textWithBreaks(body)}</div>
    </section>
  `;
}

function formatExamQuestionText(value) {
  return escapeHtml(value).replace(
    /(?:^|\s)(Questions\s+\d+\s*[-\u2013]\s*\d+)/gi,
    '<strong class="exam-question-group">$1</strong>',
  );
}

function renderPlan(data) {
  const rows = data.plan
    .map((day) => {
      const planId = Number(data.plan_id);
      const dayNumber = Number(day.day);
      const body = [
          `听力：${day.listening}`,
          `阅读：${day.reading}`,
          `写作：${day.writing}`,
          `口语：${day.speaking}`,
          `词汇：${day.vocabulary}`,
          `复盘：${day.review}`,
        ].join("\n");
      return `
        <div class="item plan-day ${day.completed ? "completed" : ""}">
          <strong>Day ${escapeHtml(dayNumber)}</strong>
          <p>${textWithBreaks(body)}</p>
          <button class="button ${day.completed ? "secondary" : "primary"}" data-plan-id="${escapeHtml(planId)}" data-plan-day="${escapeHtml(dayNumber)}" data-completed="${day.completed ? "true" : "false"}">
            ${day.completed ? "撤销完成" : "完成打卡"}
          </button>
        </div>`;
    })
    .join("");
  return `${resultHeading("学习计划", "每天按模块完成任务并打卡")}${score(`计划进度：${data.completed_days || 0}/${data.days || data.plan.length} 天（${data.progress_percent || 0}%）`)}${item("目标差距", `${data.estimated_goal_gap} 分`)}${data.next_step ? item("下一步", data.next_step) : ""}${rows}`;
}

function renderSupervisor(data) {
  if (data.agent_team) {
    const team = Object.entries(data.agent_team)
      .map(([key, value]) => item(resultLabel(key), value))
      .join("");
    return `
      ${resultHeading("主管诊断", "根据画像和错题确定当前训练重点")}
      ${score(`当前优先模块：${data.current_learning_priority}`)}
      ${item("产品概念", data.product_concept)}
      ${item("主管职责", data.supervisor_role.join("\n"))}
      ${item("选择原因", data.reason)}
      ${item("AI 主管建议", data.llm_manager_note.text)}
      ${team}
      ${item("安全措施", data.security_measures.join("\n"))}
      ${item("下一步", data.next_step)}
    `;
  }
  return `
    ${resultHeading("今日训练安排", "主管已选择最需要练习的模块")}
    ${score(`主管选择：${data.supervisor_decision.selected_agent}`)}
    ${item("选择原因", data.supervisor_decision.reason)}
    ${item("主管总结", data.manager_summary)}
    ${item("AI 主管建议", data.llm_manager_note.text)}
    ${renderSimple(data.skill_agent_result)}
    ${item("下一步", data.next_step)}
  `;
}

function renderWriting(data) {
  const criteria = Object.entries(data.criteria)
    .map(([key, value]) => item(resultLabel(key), value))
    .join("");
  return `
    ${resultHeading("写作批改结果", `${data.essay_type || "IELTS 写作"} · ${data.word_count || 0} 词`)}
    ${score(`估算 Band：${data.estimated_band_score}`)}
    ${item("说明", data.disclaimer)}
    ${criteria}
    ${item("原句问题", data.specific_problem.original_sentence)}
    ${item("为什么有问题", data.specific_problem.problem)}
    ${item("改写句", data.specific_problem.rewrite)}
    ${item("更高分表达", data.higher_band_version)}
    ${item("下一步怎么练", data.next_step)}
  `;
}

function renderSpeaking(data) {
  if (!data.feedback) {
    return `${resultHeading("口语练习题", `Part ${data.part || ""}`)}${featuredItem("主问题", data.question, "question")}${featuredItem("考官追问", data.examiner_follow_up, "question")}${item("下一步", data.next_step)}`;
  }
  const feedback = Object.entries(data.feedback)
    .map(([key, value]) => item(resultLabel(key), value))
    .join("");
  return `
    ${resultHeading("口语反馈", `Part ${data.part || ""}`)}
    ${score(`估算 Band：${data.estimated_band_score}`)}
    ${featuredItem("本次题目", data.question, "question")}
    ${feedback}
    ${item("更自然表达", data.more_natural_expression)}
    ${item("可参考答案", data.sample_answer)}
    ${item("下一步", data.next_step)}
  `;
}

function renderSimple(data) {
  if (data.passage && data.question) {
    return `
      ${resultHeading("阅读练习题", data.question_type || "阅读理解")}
      ${featuredItem("阅读材料", data.passage, "source")}
      ${featuredItem("需要回答的问题", data.question, "question", data.question_type || "")}
      ${data.strategy ? item("解题策略", data.strategy) : ""}
      ${data.next_step ? item("下一步", data.next_step) : ""}
    `;
  }
  if (data.transcript && data.question) {
    return `
      ${resultHeading("听力文本练习", data.scenario || "听力场景")}
      ${featuredItem("听力文本", data.transcript, "source")}
      ${featuredItem("需要回答的问题", data.question, "question")}
      ${data.next_step ? item("下一步", data.next_step) : ""}
    `;
  }
  return Object.entries(data)
    .filter(([_, value]) => typeof value !== "object")
    .filter(([key]) => !["audio_ready", "future_audio_api"].includes(key))
    .map(([key, value]) => item(resultLabel(key), value))
    .join("");
}

function renderVocabulary(data) {
  const cards = data.items
    .map((v) => item(v.word, `${v.meaning}\n例句：${v.example_sentence}\n搭配：${v.collocation}\n用法：${v.IELTS_usage}`))
    .join("");
  return `${resultHeading("主题词汇", `${data.topic} · 目标 Band ${data.target_band}`)}${cards}${data.next_step ? item("下一步", data.next_step) : ""}`;
}

function renderErrors(data) {
  if (!data.items.length) {
    return `<div class="empty">暂时没有错题。先提交一次写作或口语练习。</div>`;
  }
  return `${resultHeading("错题记录", `共 ${data.items.length} 条`)}${data.items
    .map((e) => item(`${e.source} / ${e.category}`, `原文：${e.original_text}\n反馈：${e.feedback}\n建议：${e.suggestion}`))
    .join("")}`;
}

function formatBytes(size) {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

function renderDocuments(data) {
  if (!data.items.length) {
    return `<div class="empty">资料库还是空的。先上传 PDF、TXT、MD、DOCX 或 PPTX 文件。</div>`;
  }
  return `${resultHeading("资料库文件", `共 ${data.items.length} 份`)}${data.items
    .map((doc) => {
      const userId = Number(doc.user_id);
      const documentId = Number(doc.id);
      return `
        <div class="item document-row">
          <div>
            <strong>${escapeHtml(doc.original_filename)}</strong>
            <p>分类：${escapeHtml(doc.category)}<br />大小：${escapeHtml(formatBytes(doc.file_size))}<br />备注：${escapeHtml(doc.notes || "无")}</p>
          </div>
          <div class="row-actions">
            <a class="button secondary" href="/documents/${encodeURIComponent(userId)}/${encodeURIComponent(documentId)}/download" target="_blank" rel="noopener">下载</a>
            <button class="button secondary danger" data-delete-document="${escapeHtml(documentId)}">删除</button>
          </div>
        </div>
      `;
    })
    .join("")}`;
}

function renderKnowledgeQuestion(data) {
  const passage = data.passage ? item("资料片段", data.passage) : "";
  return `
    ${resultHeading("资料练习题", `${data.skill} · ${data.question_type}`)}
    ${data.passage ? featuredItem("资料片段", data.passage, "source") : ""}
    ${featuredItem("需要回答的问题", data.question, "question")}
    ${item("来源", `${data.source.book}，第 ${data.source.page} 页`)}
    ${item("下一步", data.next_step)}
  `;
}

function renderKnowledgeAnalysis(data) {
  if (data.estimated_band_score !== undefined) {
    return `${renderWriting(data)}${item("资料来源", `${data.source.book}，第 ${data.source.page} 页`)}`;
  }
  return `
    ${resultHeading("答题分析", data.correct ? "回答正确" : "需要复习")}
    ${score(data.correct ? "回答正确" : "需要复习")}
    ${item("你的答案", data.your_answer)}
    ${item("标准答案", data.correct_answer)}
    ${item("原文分析", data.explanation)}
    ${item("资料来源", `${data.source.book}，第 ${data.source.page} 页`)}
    ${item("下一步", data.next_step)}
  `;
}

function renderReadingExam(data) {
  const instructions = data.instructions.map((line) => `<li>${escapeHtml(line)}</li>`).join("");
  const sections = data.sections.map((section, sectionIndex) => {
    const passageNumber = Number(section.passage_number) || sectionIndex + 1;
    const questionNumbers = Array.isArray(section.question_numbers) ? section.question_numbers : [];
    const combinedTitle = String(section.title || "");
    const inferredTitle = combinedTitle.replace(/^Reading Passage\s+\d+\s*[-\u2013:]\s*/i, "").trim();
    const articleTitle = section.article_title || inferredTitle || `Reading Passage ${passageNumber}`;
    const questionLabel = section.question_label || (questionNumbers.length
      ? `Questions ${questionNumbers[0]}-${questionNumbers[questionNumbers.length - 1]}`
      : "Questions");
    const recommendedMinutes = Number(section.recommended_minutes) || 20;
    const fields = questionNumbers.map((number) => `
      <label>Question ${number}
        <input data-exam-answer="${number}" autocomplete="off" placeholder="Answer ${number}" />
      </label>
    `).join("");
    return `
      <section class="exam-section">
        <header class="exam-section-header">
          <div class="exam-section-index">READING PASSAGE ${passageNumber}</div>
          <h3>${escapeHtml(articleTitle)}</h3>
          <p>${escapeHtml(questionLabel)} <span aria-hidden="true">·</span> 建议用时 ${recommendedMinutes} 分钟</p>
        </header>
        <div class="exam-reading-layout">
          <div class="exam-question-pane" aria-label="答题区">
            <header class="exam-pane-header exam-pane-header-questions">
              <span>答题区</span>
              <h4>${escapeHtml(questionLabel)}</h4>
            </header>
            <div class="exam-text exam-question-text exam-vocabulary-source" data-exam-section-index="${sectionIndex}" data-exam-area="questions">${formatExamQuestionText(section.questions)}</div>
            <div class="answer-grid">${fields}</div>
          </div>
          <article class="exam-passage-pane" aria-label="阅读文章">
            <header class="exam-pane-header exam-pane-header-passage">
              <span>阅读文章</span>
              <h4>${escapeHtml(articleTitle)}</h4>
            </header>
            <div class="exam-text exam-vocabulary-source" data-exam-section-index="${sectionIndex}" data-exam-area="passage">${escapeHtml(section.passage)}</div>
          </article>
        </div>
      </section>
    `;
  }).join("");
  return `
    <div class="score">${escapeHtml(data.title)}</div>
    <ul>${instructions}</ul>
    ${item("资料来源", `${escapeHtml(data.source.book)}，答案页 ${data.source.answer_key_page}`)}
    <aside class="vocabulary-helper" aria-label="题目词汇解释工具">
      <div>
        <strong>题目词汇助手</strong>
        <p id="selectedVocabularyText">题目、选项和原文中的英文都可以左键拖选；松开后自动标亮并分析，也可以双击单词。</p>
      </div>
      <button class="button secondary" id="explainExamVocabularyButton" type="button" disabled>重新解释</button>
      <div id="examVocabularyResult" class="vocabulary-result"></div>
    </aside>
    ${sections}
  `;
}

function renderExamVocabulary(data) {
  const provider = data.provider === "local_dictionary"
    ? `本机离线词典${data.dictionary_source ? `（${data.dictionary_source}）` : ""}`
    : data.provider === "configured_llm"
      ? "已配置 AI 模型"
      : data.provider === "public_dictionary"
        ? "公开英英词典与翻译服务"
        : "离线提示";
  return `
    <div class="vocabulary-result-header">
      <div class="vocabulary-word"><strong>${escapeHtml(data.term)}</strong><span>${escapeHtml(data.part_of_speech)}</span></div>
      <button class="button secondary" id="closeVocabularyResult" type="button" aria-label="关闭词汇解释">关闭</button>
    </div>
    ${item("中文释义", data.meaning_zh)}
    ${item("在本题中的意思", data.context_meaning_zh)}
    ${item("简单英文解释", data.simple_english)}
    ${item("记忆提示", data.memory_tip)}
    ${item("例句", data.example)}
    ${item("真题语境", data.context)}
    ${item("解释方式", provider)}
    ${item("资料来源", `${data.source.book}，第 ${data.source.pages.join("、")} 页`)}
  `;
}

function renderExamVocabularyLoading(term) {
  return `
    <div class="vocabulary-result-header">
      <div class="vocabulary-word"><strong>${escapeHtml(term)}</strong><span>分析中</span></div>
      <button class="button secondary" id="closeVocabularyResult" type="button" aria-label="关闭词汇解释">关闭</button>
    </div>
    <div class="empty" role="status">正在解释“${escapeHtml(term)}”...</div>
  `;
}

function closeExamVocabularyResult() {
  clearTimeout(examVocabularyTimer);
  examVocabularyRequestId += 1;
  const target = $("examVocabularyResult");
  const button = $("explainExamVocabularyButton");
  const label = $("selectedVocabularyText");
  if (target) target.replaceChildren();
  if (button) {
    button.disabled = !selectedExamVocabulary;
    button.textContent = "重新解释";
  }
  if (label && selectedExamVocabulary) label.textContent = `已选中：${selectedExamVocabulary.term}`;
}

function renderReadingExamGrade(data) {
  const sectionScores = Object.entries(data.analysis.section_scores)
    .map(([name, score]) => `${name}：${score}`)
    .join("\n");
  const details = data.details.map((row) => `
    <div class="item ${row.correct ? "answer-correct" : "answer-wrong"}">
      <strong>Question ${row.number} · ${row.correct ? "Correct" : "Incorrect"}</strong>
      <p>你的答案：${escapeHtml(row.your_answer)}<br />正确答案：${escapeHtml(row.correct_answer)}</p>
    </div>
  `).join("");
  return `
    ${resultHeading("模考成绩", "40 道题已完成统一判分")}
    <div class="score">Raw Score ${data.raw_score}/40 · Estimated Band ${data.estimated_band}</div>
    ${item("分篇表现", sectionScores)}
    ${item("重点复盘", data.analysis.next_step)}
    ${item("说明", data.disclaimer)}
    ${details}
  `;
}

function updateExamTimer() {
  const minutes = Math.floor(examSecondsLeft / 60).toString().padStart(2, "0");
  const seconds = (examSecondsLeft % 60).toString().padStart(2, "0");
  $("examTimer").textContent = `${minutes}:${seconds}`;
  if (examSecondsLeft <= 0) {
    clearInterval(examTimerHandle);
    submitReadingExam();
    return;
  }
  examSecondsLeft -= 1;
}

async function startReadingExam() {
  const target = $("readingExamResult");
  try {
    showLoading(target, "正在从 Cambridge IELTS 16 读取完整试卷...");
    readingExam = await api("/exam/reading/start");
    target.innerHTML = renderReadingExam(readingExam);
    selectedExamVocabulary = null;
    selectedExamRange = null;
    clearTimeout(examVocabularyTimer);
    examVocabularyRequestId += 1;
    examSecondsLeft = readingExam.duration_minutes * 60;
    clearInterval(examTimerHandle);
    updateExamTimer();
    examTimerHandle = setInterval(updateExamTimer, 1000);
  } catch (error) {
    showError(target, error);
  }
}

async function submitReadingExam() {
  const target = $("readingExamResult");
  try {
    const answers = {};
    document.querySelectorAll("[data-exam-answer]").forEach((input) => {
      answers[input.dataset.examAnswer] = input.value.trim();
    });
    clearInterval(examTimerHandle);
    showLoading(target, "正在按 40 道题统一判分并分析...");
    const data = await api("/exam/reading/submit", {
      method: "POST",
      body: JSON.stringify({ user_id: requireUser(), answers }),
    });
    target.innerHTML = renderReadingExamGrade(data);
  } catch (error) {
    showError(target, error);
  }
}

$("startReadingExamButton").addEventListener("click", startReadingExam);
$("submitReadingExamButton").addEventListener("click", submitReadingExam);

function captureExamVocabulary(term, sourceBlock, range) {
  const normalized = term.replace(/\s+/g, " ").trim().replace(/^[^A-Za-z]+|[^A-Za-z]+$/g, "");
  if (!/^[A-Za-z][A-Za-z' -]{0,79}$/.test(normalized)) return;
  selectedExamVocabulary = {
    term: normalized,
    sectionIndex: Number(sourceBlock.dataset.examSectionIndex),
    area: sourceBlock.dataset.examArea,
  };
  selectedExamRange = range.cloneRange();
  const label = $("selectedVocabularyText");
  const button = $("explainExamVocabularyButton");
  if (label) label.textContent = `已选中：${normalized}，正在自动分析...`;
  if (button) button.disabled = true;
  clearTimeout(examVocabularyTimer);
  examVocabularyTimer = setTimeout(() => explainSelectedExamVocabulary(), 180);
}

function highlightSelectedExamVocabulary() {
  if (!selectedExamRange) return;
  const commonContainer = selectedExamRange.commonAncestorContainer;
  const container = commonContainer.nodeType === 1 ? commonContainer : commonContainer.parentElement;
  if (container?.closest?.(".vocabulary-highlight")) return;
  const mark = document.createElement("mark");
  mark.className = "vocabulary-highlight";
  try {
    selectedExamRange.surroundContents(mark);
  } catch (_) {
    // Multi-node phrases can still be explained even when one mark cannot wrap them.
  }
}

async function explainSelectedExamVocabulary() {
  if (!selectedExamVocabulary) return;
  const target = $("examVocabularyResult");
  const button = $("explainExamVocabularyButton");
  const selectionSnapshot = { ...selectedExamVocabulary };
  const requestId = ++examVocabularyRequestId;
  highlightSelectedExamVocabulary();
  if (button) {
    button.disabled = true;
    button.textContent = "分析中...";
  }
  target.innerHTML = renderExamVocabularyLoading(selectionSnapshot.term);
  try {
    const data = await api("/exam/vocabulary/explain", {
      method: "POST",
      body: JSON.stringify({
        term: selectionSnapshot.term,
        section_index: selectionSnapshot.sectionIndex,
        area: selectionSnapshot.area,
      }),
    });
    if (requestId !== examVocabularyRequestId) return;
    target.innerHTML = renderExamVocabulary(data);
    const label = $("selectedVocabularyText");
    if (label) label.textContent = `已分析：${selectionSnapshot.term}`;
  } catch (error) {
    if (requestId === examVocabularyRequestId) showError(target, error);
  } finally {
    if (requestId === examVocabularyRequestId && button) {
      button.disabled = false;
      button.textContent = "重新解释";
    }
  }
}

document.addEventListener("mousedown", (event) => {
  if (event.button !== 0 || !document.caretRangeFromPoint) return;
  const sourceBlock = event.target.closest?.(".exam-vocabulary-source");
  if (!sourceBlock) return;
  const caret = document.caretRangeFromPoint(event.clientX, event.clientY);
  if (!caret?.startContainer || !sourceBlock.contains(caret.startContainer)) return;
  examVocabularyDragStart = {
    sourceBlock,
    node: caret.startContainer,
    offset: caret.startOffset,
  };
});

document.addEventListener("mouseup", (event) => {
  const selection = window.getSelection();
  let range = selection && selection.rangeCount > 0 && !selection.isCollapsed
    ? selection.getRangeAt(0)
    : null;

  if (!range && examVocabularyDragStart && document.caretRangeFromPoint) {
    const endCaret = document.caretRangeFromPoint(event.clientX, event.clientY);
    if (endCaret?.startContainer === examVocabularyDragStart.node && endCaret.startOffset !== examVocabularyDragStart.offset) {
      range = document.createRange();
      const startOffset = Math.min(examVocabularyDragStart.offset, endCaret.startOffset);
      const endOffset = Math.max(examVocabularyDragStart.offset, endCaret.startOffset);
      range.setStart(examVocabularyDragStart.node, startOffset);
      range.setEnd(examVocabularyDragStart.node, endOffset);
      selection.removeAllRanges();
      selection.addRange(range);
    }
  }
  examVocabularyDragStart = null;
  if (!range) return;
  const startElement = range.startContainer.nodeType === 1 ? range.startContainer : range.startContainer.parentElement;
  const endElement = range.endContainer.nodeType === 1 ? range.endContainer : range.endContainer.parentElement;
  const sourceBlock = startElement?.closest?.(".exam-vocabulary-source");
  if (!sourceBlock || !sourceBlock.contains(endElement)) return;

  captureExamVocabulary(selection.toString(), sourceBlock, range);
});

document.addEventListener("dblclick", (event) => {
  const sourceBlock = event.target.closest?.(".exam-vocabulary-source");
  if (!sourceBlock || !document.caretRangeFromPoint) return;
  const caret = document.caretRangeFromPoint(event.clientX, event.clientY);
  const textNode = caret?.startContainer;
  if (!textNode || textNode.nodeType !== Node.TEXT_NODE || !sourceBlock.contains(textNode)) return;
  const text = textNode.textContent || "";
  let start = caret.startOffset;
  let end = caret.startOffset;
  while (start > 0 && /[A-Za-z'-]/.test(text[start - 1])) start -= 1;
  while (end < text.length && /[A-Za-z'-]/.test(text[end])) end += 1;
  if (start === end) return;
  const range = document.createRange();
  range.setStart(textNode, start);
  range.setEnd(textNode, end);
  const selection = window.getSelection();
  selection.removeAllRanges();
  selection.addRange(range);
  captureExamVocabulary(range.toString(), sourceBlock, range);
});

document.addEventListener("click", (event) => {
  const button = event.target.closest("#explainExamVocabularyButton");
  if (!button || !selectedExamVocabulary) return;
  clearTimeout(examVocabularyTimer);
  explainSelectedExamVocabulary();
});

document.addEventListener("click", (event) => {
  if (!event.target.closest("#closeVocabularyResult")) return;
  closeExamVocabularyResult();
});

document.addEventListener("keydown", (event) => {
  const target = $("examVocabularyResult");
  if (event.key !== "Escape" || !target?.children.length) return;
  closeExamVocabularyResult();
});

function profilePayload() {
  const form = new FormData($("profileForm"));
  return {
    current_band: Number(form.get("current_band")),
    target_band: Number(form.get("target_band")),
    prep_days: Number(form.get("prep_days")),
    daily_minutes: Number(form.get("daily_minutes")),
    weak_skills: String(form.get("weak_skills")).split(",").map((value) => value.trim()).filter(Boolean),
    focus_areas: String(form.get("focus_areas")).split(",").map((value) => value.trim()).filter(Boolean),
  };
}

function fillProfileForm(profile) {
  const form = $("profileForm");
  form.elements.current_band.value = profile.current_band;
  form.elements.target_band.value = profile.target_band;
  form.elements.prep_days.value = profile.prep_days;
  form.elements.daily_minutes.value = profile.daily_minutes;
  form.elements.weak_skills.value = profile.weak_skills.join(",");
  form.elements.focus_areas.value = profile.focus_areas.join(",");
}

$("profileForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const target = $("currentUserId");
  const button = $("profileCreateButton");
  const payload = profilePayload();
  try {
    await withButtonLoading(button, "创建中...", async () => {
      const data = await api("/profile/create", { method: "POST", body: JSON.stringify(payload) });
      setUser(data.id);
      switchView("supervisor");
    });
  } catch (error) {
    target.textContent = error.message;
  }
});

$("profileLoadButton").addEventListener("click", async () => {
  const target = $("currentUserId");
  try {
    const data = await withButtonLoading($("profileLoadButton"), "读取中...", () => api(`/profile/${requireUser()}`));
    fillProfileForm(data);
    target.textContent = `${data.id}（画像已读取）`;
  } catch (error) {
    target.textContent = error.message;
  }
});

$("profileUpdateButton").addEventListener("click", async () => {
  const target = $("currentUserId");
  try {
    const data = await withButtonLoading($("profileUpdateButton"), "保存中...", () => api(`/profile/${requireUser()}`, {
      method: "PUT",
      body: JSON.stringify(profilePayload()),
    }));
    fillProfileForm(data);
    target.textContent = `${data.id}（画像已更新）`;
  } catch (error) {
    target.textContent = error.message;
  }
});

$("profileDeleteButton").addEventListener("click", async () => {
  const userId = requireUser();
  if (!window.confirm("将删除当前画像及其计划、错题、词汇和资料，确定继续吗？")) return;
  const target = $("currentUserId");
  try {
    await withButtonLoading($("profileDeleteButton"), "删除中...", () => api(`/profile/${userId}`, { method: "DELETE" }));
    localStorage.removeItem("ielts_user_id");
    currentUserId = null;
    target.textContent = "画像已删除";
  } catch (error) {
    target.textContent = error.message;
  }
});

$("generatePlanButton").addEventListener("click", async () => {
  const target = $("planResult");
  try {
    showLoading(target, "正在生成学习计划...");
    await withButtonLoading($("generatePlanButton"), "生成中...", async () => {
      const data = await api("/study-plan/generate", {
        method: "POST",
        body: JSON.stringify({ user_id: requireUser(), days: Number($("planDays").value) }),
      });
      target.innerHTML = renderPlan(data);
    });
  } catch (error) {
    showError(target, error);
  }
});

async function loadLatestPlan() {
  const target = $("planResult");
  try {
    showLoading(target, "正在读取最近的学习计划...");
    const data = await api(`/study-plan/${requireUser()}/latest`);
    target.innerHTML = renderPlan(data);
  } catch (error) {
    showError(target, error);
  }
}

$("loadLatestPlanButton").addEventListener("click", loadLatestPlan);

$("diagnoseSupervisorButton").addEventListener("click", async () => {
  const target = $("supervisorResult");
  try {
    showLoading(target, "主管 Agent 正在读取画像和错题...");
    await withButtonLoading($("diagnoseSupervisorButton"), "诊断中...", async () => {
      const data = await api("/supervisor/diagnose", {
        method: "POST",
        body: JSON.stringify({ user_id: requireUser() }),
      });
      target.innerHTML = renderSupervisor(data);
    });
  } catch (error) {
    showError(target, error);
  }
});

$("coachSupervisorButton").addEventListener("click", async () => {
  const target = $("supervisorResult");
  try {
    showLoading(target, "主管 Agent 正在分配训练任务...");
    await withButtonLoading($("coachSupervisorButton"), "安排中...", async () => {
      const data = await api("/supervisor/coach", {
        method: "POST",
        body: JSON.stringify({
          user_id: requireUser(),
          skill_focus: $("supervisorSkill").value || null,
          learner_input: $("supervisorInput").value.trim() || null,
          speaking_part: Number($("supervisorSpeakingPart").value),
        }),
      });
      target.innerHTML = renderSupervisor(data);
    });
  } catch (error) {
    showError(target, error);
  }
});

$("reviewWritingButton").addEventListener("click", async () => {
  const target = $("writingResult");
  try {
    showLoading(target, "写作 Agent 正在批改...");
    await withButtonLoading($("reviewWritingButton"), "批改中...", async () => {
      const data = await api("/writing/review", {
        method: "POST",
        body: JSON.stringify({ user_id: requireUser(), task_type: $("taskType").value, essay_text: $("essayText").value }),
      });
      target.innerHTML = renderWriting(data);
    });
  } catch (error) {
    showError(target, error);
  }
});

$("practiceSpeakingButton").addEventListener("click", async () => {
  const target = $("speakingResult");
  try {
    const answer = $("speakingAnswer").value.trim();
    showLoading(target, "口语 Agent 正在准备反馈...");
    await withButtonLoading($("practiceSpeakingButton"), "处理中...", async () => {
      const data = await api("/speaking/practice", {
        method: "POST",
        body: JSON.stringify({ user_id: requireUser(), part: Number($("speakingPart").value), answer_text: answer || null }),
      });
      target.innerHTML = renderSpeaking(data);
    });
  } catch (error) {
    showError(target, error);
  }
});

$("practiceReadingButton").addEventListener("click", async () => {
  const target = $("readingResult");
  try {
    const answer = $("readingAnswer").value.trim();
    showLoading(target, "阅读 Agent 正在生成或批改题目...");
    await withButtonLoading($("practiceReadingButton"), "处理中...", async () => {
      const data = await api("/reading/practice", {
        method: "POST",
        body: JSON.stringify({ user_id: requireUser(), user_answer: answer || null }),
      });
      target.innerHTML = renderSimple(data);
    });
  } catch (error) {
    showError(target, error);
  }
});

$("practiceListeningButton").addEventListener("click", async () => {
  const target = $("listeningResult");
  try {
    const answer = $("listeningAnswer").value.trim();
    showLoading(target, "听力 Agent 正在生成或批改题目...");
    await withButtonLoading($("practiceListeningButton"), "处理中...", async () => {
      const data = await api("/listening/practice", {
        method: "POST",
        body: JSON.stringify({ user_id: requireUser(), user_answer: answer || null }),
      });
      target.innerHTML = renderSimple(data);
    });
  } catch (error) {
    showError(target, error);
  }
});

$("generateVocabButton").addEventListener("click", async () => {
  const target = $("vocabResult");
  try {
    showLoading(target, "词汇 Agent 正在生成主题词汇...");
    await withButtonLoading($("generateVocabButton"), "生成中...", async () => {
      const data = await api("/vocabulary/generate", {
        method: "POST",
        body: JSON.stringify({ user_id: requireUser(), topic: $("vocabTopic").value, count: 8 }),
      });
      target.innerHTML = renderVocabulary(data);
    });
  } catch (error) {
    showError(target, error);
  }
});

async function loadErrors() {
  const target = $("errorsResult");
  try {
    showLoading(target, "正在读取错题本...");
    const data = await api(`/errors/${requireUser()}`);
    target.innerHTML = renderErrors(data);
  } catch (error) {
    showError(target, error);
  }
}

async function loadDocuments() {
  const target = $("documentsResult");
  try {
    showLoading(target, "正在读取资料库...");
    const data = await api(`/documents/${requireUser()}`);
    target.innerHTML = renderDocuments(data);
    if (!currentKnowledgeQuestionId) {
      await generateKnowledgeQuestion();
    }
  } catch (error) {
    showError(target, error);
  }
}

$("documentForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const target = $("documentsResult");
  const file = $("documentFile").files[0];
  if (!file) {
    showError(target, new Error("请先选择一个文件。"));
    return;
  }
  try {
    showLoading(target, "正在上传文件...");
    await withButtonLoading($("uploadDocumentButton"), "上传中...", async () => {
      const form = new FormData();
      form.append("user_id", String(requireUser()));
      form.append("category", $("documentCategory").value);
      form.append("notes", $("documentNotes").value.trim());
      form.append("file", file);
      const response = await fetch("/documents/upload", { method: "POST", body: form });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "上传失败");
      }
      $("documentFile").value = "";
      target.innerHTML = item("上传成功", `${data.item.original_filename}\n${data.next_step}`);
      await loadDocuments();
    });
  } catch (error) {
    showError(target, error);
  }
});

$("refreshDocumentsButton").addEventListener("click", loadDocuments);

async function generateKnowledgeQuestion(append = false) {
  const target = $("knowledgeResult");
  try {
    if (!append) {
      showLoading(target, "主管正在根据你的弱项从资料中出题...");
    }
    const requestQuestion = async () => {
      const data = await api("/knowledge/question", {
        method: "POST",
        body: JSON.stringify({
          user_id: requireUser(),
          skill: $("knowledgeSkill").value,
          topic: $("knowledgeTopic").value.trim() || null,
        }),
      });
      currentKnowledgeQuestionId = data.question_id;
      $("knowledgeAnswer").value = "";
      const rendered = renderKnowledgeQuestion(data);
      if (append) {
        target.insertAdjacentHTML("beforeend", `<hr />${item("主管已主动准备下一题", "直接在上方答案框继续作答。")}${rendered}`);
      } else {
        target.innerHTML = rendered;
      }
    };
    if (append) {
      await requestQuestion();
    } else {
      await withButtonLoading($("knowledgeQuestionButton"), "出题中...", requestQuestion);
    }
  } catch (error) {
    showError(target, error);
  }
}

$("knowledgeQuestionButton").addEventListener("click", () => generateKnowledgeQuestion(false));

$("knowledgeAnalyzeButton").addEventListener("click", async () => {
  const target = $("knowledgeResult");
  try {
    if (!currentKnowledgeQuestionId) throw new Error("请先生成一道资料题。");
    const answer = $("knowledgeAnswer").value.trim();
    if (!answer) throw new Error("请先填写答案。");
    showLoading(target, "正在对照原资料分析答案...");
    await withButtonLoading($("knowledgeAnalyzeButton"), "分析中...", async () => {
      const data = await api("/knowledge/analyze", {
        method: "POST",
        body: JSON.stringify({ user_id: requireUser(), question_id: currentKnowledgeQuestionId, answer }),
      });
      target.innerHTML = renderKnowledgeAnalysis(data);
      await generateKnowledgeQuestion(true);
    });
  } catch (error) {
    showError(target, error);
  }
});

document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-plan-day]");
  if (!button) return;
  const planId = Number(button.dataset.planId);
  const dayNumber = Number(button.dataset.planDay);
  const completed = button.dataset.completed === "true";
  const target = $("planResult");
  if (!Number.isInteger(planId) || !Number.isInteger(dayNumber)) {
    showError(target, new Error("计划数据无效，请重新生成计划。"));
    return;
  }
  try {
    await withButtonLoading(button, "保存中...", async () => {
      const data = await api(`/study-plan/${requireUser()}/${planId}/days/${dayNumber}`, {
        method: "PATCH",
        body: JSON.stringify({ completed: !completed }),
      });
      target.innerHTML = renderPlan(data);
    });
  } catch (error) {
    showError(target, error);
  }
});

document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-delete-document]");
  if (!button) {
    return;
  }
  const documentId = button.dataset.deleteDocument;
  const target = $("documentsResult");
  try {
    await withButtonLoading(button, "删除中...", async () => {
      const response = await fetch(`/documents/${requireUser()}/${documentId}`, { method: "DELETE" });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "删除失败");
      }
      await loadDocuments();
    });
  } catch (error) {
    showError(target, error);
  }
});

$("refreshErrorsButton").addEventListener("click", loadErrors);

document.addEventListener("click", async (event) => {
  const link = event.target.closest("[data-view-link]");
  if (!link) {
    return;
  }
  event.preventDefault();
  const viewName = link.dataset.viewLink;
  switchView(viewName);
  if (viewName === "library" && !readingExam) {
    await startReadingExam();
  }
});

document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-tool-link]");
  if (!button) return;
  const toolName = button.dataset.toolLink;
  const targetTool = document.querySelector(`[data-tool="${toolName}"]`);
  if (!targetTool) return;
  switchView(targetTool.dataset.toolGroup, true, toolName);
  if (toolName === "errors") await loadErrors();
  if (toolName === "documents") await loadDocuments();
  if (toolName === "exam" && !readingExam) await startReadingExam();
});

window.addEventListener("hashchange", () => {
  switchView(window.location.hash.replace("#", "") || "today", false);
});

if (currentUserId) {
  $("currentUserId").textContent = currentUserId;
}

const initialView = window.location.hash.replace("#", "") || "today";
switchView(initialView, false);
refreshServiceStatus();
if (initialView === "documents" && currentUserId) {
  loadDocuments();
}
if ((initialView === "exam" || initialView === "library") && currentUserId) {
  startReadingExam();
}

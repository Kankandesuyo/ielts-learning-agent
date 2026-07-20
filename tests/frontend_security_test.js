const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const inertElement = () => ({
  addEventListener() {},
  classList: { add() {}, remove() {}, toggle() {} },
  querySelector() { return inertElement(); },
  replaceChildren() {},
  textContent: "",
  value: "",
  files: [],
  elements: {},
});

const sandbox = {
  console,
  fetch: async () => ({ ok: true, json: async () => ({ status: "ok" }) }),
  FormData: class { get() { return ""; } append() {} },
  localStorage: { getItem() { return null; }, setItem() {}, removeItem() {} },
  document: {
    getElementById() { return inertElement(); },
    querySelector() { return inertElement(); },
    querySelectorAll() { return []; },
    addEventListener() {},
    createElement() { return inertElement(); },
  },
  window: {
    addEventListener() {},
    confirm() { return false; },
    history: { pushState() {} },
    location: { hash: "" },
  },
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("app/static/app.js", "utf8"), sandbox);

const payload = '<img src=x onerror="globalThis.xss=true">';
assert.equal(sandbox.escapeHtml(payload).includes("<img"), false);
assert.equal(sandbox.escapeHtml(payload).includes("&lt;img"), true);
assert.equal(sandbox.item("备注", payload).includes("<img"), false);

const rendered = sandbox.renderDocuments({
  items: [{ id: 1, user_id: 1, original_filename: payload, category: "notes", file_size: 10, notes: payload }],
});
assert.equal(rendered.includes("<img"), false);
assert.equal(rendered.includes("&lt;img"), true);

const examHtml = sandbox.renderReadingExam({
  title: "Reading Test",
  instructions: [],
  source: { book: "book.pdf", answer_key_page: 1 },
  sections: [{
    passage_number: 1,
    article_title: "A clearly separated title",
    question_label: "Questions 1-2",
    recommended_minutes: 20,
    questions: "1 First question 2 Second question",
    passage: "Article body starts here.",
    question_numbers: [1, 2],
  }],
});
assert.equal(examHtml.includes("READING PASSAGE 1"), true);
assert.equal(examHtml.includes("A clearly separated title"), true);
assert.equal(examHtml.includes("答题区"), true);
assert.equal(examHtml.includes("Article body starts here."), true);

const readingPracticeHtml = sandbox.renderSimple({
  passage: payload,
  question_type: "True / False / Not Given",
  question: "Is the statement supported?",
  strategy: "Locate the matching sentence.",
  next_step: "Choose one answer.",
});
assert.equal(readingPracticeHtml.includes("阅读练习题"), true);
assert.equal(readingPracticeHtml.includes("需要回答的问题"), true);
assert.equal(readingPracticeHtml.includes("<img"), false);
assert.equal(readingPracticeHtml.includes("&lt;img"), true);

const groupedQuestions = sandbox.formatExamQuestionText("Questions 1-7 First group Questions 8-13 Second group");
assert.equal((groupedQuestions.match(/exam-question-group/g) || []).length, 2);

const futureExamHtml = sandbox.renderReadingExam({
  title: "Future exam",
  instructions: [],
  source: { book: "future.pdf", answer_key_page: 99 },
  sections: [{
    title: "Reading Passage 4 - A new article from another book",
    questions: "Questions 41 – 42 Read the text.",
    passage: "A different article body.",
    question_numbers: [41, 42],
  }],
});
assert.equal(futureExamHtml.includes("A new article from another book"), true);
assert.equal(futureExamHtml.includes("Questions 41-42"), true);
assert.equal(futureExamHtml.includes("undefined"), false);

console.log("Frontend XSS escaping checks passed.");

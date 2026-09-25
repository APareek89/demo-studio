// Short holding lines, never answers or a claim that a web search has happened.
// Each visit walks the whole pool before repeating; the player owns when to speak.
export const QUESTION_ACKNOWLEDGEMENTS = Object.freeze([
  "Let me check that for you.",
  "I'll check the details.",
  "One moment while I look that up.",
  "Let me take a closer look.",
  "I'll see what the information says.",
  "Give me a moment to check.",
  "Let me look into that.",
  "I'll check what's available.",
  "Let me find the relevant details.",
  "Just a moment while I check that.",
]);

export function nextQuestionAcknowledgement(visit, fillers = {}) {
  const index = Number.isSafeInteger(visit.questionAckIndex) && visit.questionAckIndex >= 0 ? visit.questionAckIndex : 0;
  const text = QUESTION_ACKNOWLEDGEMENTS[index % QUESTION_ACKNOWLEDGEMENTS.length];
  visit.questionAckIndex = (index + 1) % QUESTION_ACKNOWLEDGEMENTS.length;
  // Old publications work without rebuilding: reuse only an exact matching
  // recorded line; otherwise speak() uses the existing locked runtime voice.
  const recorded = Object.values(fillers).find(item => item?.text === text && item.audio);
  return { text, audio: recorded?.audio || null };
}

// research-skill: ships the daily-stock-research skill from inside a plugin via
// the ctx.skills runtime registry, instead of relying on a .dsh/skills file on
// disk. Demonstrates a plugin that contributes a skill.

import { SKILL_BODY } from "@stock-trader/dsh-plugin-shared/research-text";

export const name = "research-skill";
export const inject = ["skills"];

export function apply(ctx: {
  skills: {
    register: (skill: {
      name: string;
      description: string;
      whenToUse?: string;
      content: string;
      source: string;
      invocation: { modelInvocable: boolean; userInvocable: boolean };
    }) => unknown;
  };
}): void {
  // Register during apply, like the tool plugins.
  const skills = ctx.skills;
  skills.register({
    name: "daily-stock-research",
    description: "Run the fixture-backed A-share after-close research flow. Use when the user asks for 盘后研究, 每日研究, 选股报告, or asks to load daily-stock-research.",
    whenToUse: "盘后研究 / 每日研究 / 选股报告 / 加载 daily-stock-research",
    content: SKILL_BODY,
    source: "plugin:research-skill",
    invocation: { modelInvocable: true, userInvocable: true },
  });
}

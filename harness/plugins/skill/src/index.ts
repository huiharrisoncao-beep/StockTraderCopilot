// research-skill: ships the stock-research-pipeline skill from inside a plugin
// via the ctx.skills runtime registry, instead of relying on a .dsh/skills file
// on disk. Named distinctly from the filesystem daily-stock-research skill so
// both coexist and the plugin-shipped one is not shadowed by the project skill.

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
    name: "stock-research-pipeline",
    description: "Run the fixture-backed A-share after-close research pipeline (market snapshot, screening, per-stock research, risk, report). Use when the user asks for 盘后研究, 每日研究, 选股报告, or asks to load stock-research-pipeline.",
    whenToUse: "盘后研究 / 每日研究 / 选股报告 / 加载 stock-research-pipeline",
    content: SKILL_BODY,
    source: "plugin:research-skill",
    invocation: { modelInvocable: true, userInvocable: true },
  });
}

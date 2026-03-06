# Project Overview

## Summary

This project is a **metroidvania** game developed as a web-based PWA. It is built for incremental growth, rapid prototyping, and experimentation with agentic development workflows.

---

## 1. Game & Scope

- **Genre:** Metroidvania (exploration, backtracking, ability-gated progression).
- **Development model:** The game will **grow incrementally**—features, areas, and mechanics are added over time rather than built in one shot.

---

## 2. Tech Stack & Hosting

- **Rapid prototyping** using standard web technologies: **HTML**, **JavaScript**, and related web APIs.
- **Hosting:** Deployed as a **Progressive Web App (PWA)** via **GitHub Pages** for easy sharing and installable experience.

---

## 3. Agentic Workflows

- The project is used as a **gauge for testing agentic workflows**—e.g. AI-assisted coding, automated refactors, and agent-driven feature implementation.
- Documentation and structure (including this overview and `project_plan.md`) support both human and AI contributors.

---

## 4. Architecture

- **Monolithic:** The main application lives in a **single `index.html`** file.
- All game logic, styles, and scripts are contained there to keep the prototype simple and portable.

---

## 5. Code Style Priorities

HTML and in-file code shall be **clean and readable**, with priorities in this order:

1. **Generic AI coding agent interpretation** — Structure and naming should be easy for any coding agent to parse and modify.
2. **Execution efficiency** — Prefer clear, efficient algorithms and minimal unnecessary work.
3. **Reliability** — Code should be predictable and robust under normal use.

---

## 6. Project Plan

- A **`project_plan.md`** file is maintained in **`./prompts/`** and should be **kept up to date** with current goals, milestones, and next steps.

---

## 7. Tests

- **Tests** are stored under **`./tests/`**.
- Test coverage and layout should be maintained there as the project grows.

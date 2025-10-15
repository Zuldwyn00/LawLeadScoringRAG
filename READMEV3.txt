---

Legal Lead Scoring AI System

Overview

This application generates AI-based lead scores for legal cases using firm data. It combines a modular backend for different AI tools with an iterative scoring process that refines itself through multiple data passes and user feedback.


---

Usage

Run by launching legal_lead.bat in the main folder.


---

How Lead Scoring Works
________________

1. Input:
Enter a lead in plain text into the input box. After a few minutes, a lead score will be generated. The score is saved automatically and reloaded on startup.


2. Viewing & Feedback:

Leads are stored with expandable details for full explanations.

Users can modify any score directly in the UI for feedback.

Text in the AI analysis can be edited or highlighted — all changes are logged for later refinement.



3. Iterative Scoring Process:

The AI refines its understanding over several passes, using tool calls to retrieve more data.

The process stops after a set limit or when a confidence threshold is reached.

These parameters can be adjusted in the UI to balance speed, accuracy, and cost.



4. Summarization System:

Long case files are summarized automatically by a separate model before scoring.

Summaries are stored in cache JSON files using hash-based partitioning (50-file structure) for fast access and minimal redundancy.

Cached summaries can be reused across multiple scoring sessions to lower cost and speed up processing.



---

Lead Discussion
_______________

Each lead can be opened in a discussion window where the user can talk directly with the AI about that case. The AI uses the lead data to:

* Explain how it reached a score.

* Find missing information or similar cases.

* Suggest next steps.


Important text is highlighted for easier reading, with color emphasis added in the UI.


---

Backend Details
_______________

* Built on a modular tool framework that allows adding new AI agents and tools easily.

* Configurable iterative scoring limits

* Cost tracking and optimization

* PPI protection adherence for personal data protection and protection from having AI discuss internal processes.
(can be more refined, currently the protections in place are fine for the current scale and useage, but would need more refinement for real-world scale.)


* Includes optional jurisdiction-based modifiers (Bayesian shrinkage) that adjust scores based on available settlement data.

* Caching and configuration files are handled with simple JSON structures for easy debugging and portability.



---

Jurisdiction Scoring (Currently Disabled)
________________

A jurisdiction-based scoring algorithm is included but disabled due to inconsistent real-world data.
It adjusts scores based on historical case outcomes using Bayesian shrinkage to account for limited samples.

When data is sufficient, the system modifies scores based on how reliable each jurisdiction’s statistics are.
High-data areas retain stronger weighting; low-data areas revert toward the global average.
The system remains fully implemented and can be reactivated if consistent settlement data becomes available

---

Notes
________________

This project was built for internal firm use and is designed for flexibility and easy expansion — new tools, models, or scoring strategies can be added with minimal code changes.



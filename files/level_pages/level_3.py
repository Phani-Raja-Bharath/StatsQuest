import streamlit as st


def render(ctx):
    pid = ctx.pid

    st.header(ctx.STORY["levels"][3])
    st.caption("Level 3 follows four steps: Watch, Explore, Try, and Apply.")

    ctx.show_step_header(
        "Step 1 - Watch",
        "Before starting this level, watch the short videos. Together they cover Normal, Uniform, "
        "Bernoulli, Binomial, and Poisson distributions.",
    )
    ctx.show_youtube_resources("level_3")
    watched = ctx.show_video_acknowledgement(pid, 3, "L3_VIDEO_ACK", key="l3_video_ack")
    if not watched:
        st.info("Complete Step 1 before starting the activity.")
        ctx.show_level_progress(pid, 3)
        ctx.show_next_button()
        return

    ctx.show_step_header(
        "Step 2 - Explore",
        "Use the reference card below to match the first situation to a distribution.",
    )
    ctx.show_distribution_reference()

    ctx.show_challenge_acknowledgement(pid, "L3_Q1")
    st.markdown("**Sensor measurement noise** clustered around a target value")
    st.info("💡 Values that cluster around an average, with most close to it and fewer far away, describe a **Normal** distribution.")
    explore_answer = ctx.answer_radio("Choose the **matching distribution**.", ["Normal", "Poisson", "Bernoulli", "Uniform"], key="L3_Q1")
    if st.button("Submit Explore answer", key="L3_Q1_submit"):
        ctx.score_answer(
            pid,
            3,
            "L3_Q1",
            explore_answer,
            explore_answer == "Normal",
            20,
            correct_answer="Normal",
            explanation="Normal values cluster around an average.",
            stage="explore",
        )

    if not ctx.is_stage_complete(pid, "L3_Q1"):
        st.info("Complete Step 2 to unlock Step 3.")
        ctx.show_level_progress(pid, 3)
        ctx.show_next_button()
        return

    ctx.show_step_header(
        "Step 3 - Try",
        "Now match a second situation.",
    )
    with st.expander("Distribution quick reference"):
        ctx.show_distribution_reference()

    ctx.show_challenge_acknowledgement(pid, "L3_Q2")
    st.markdown("One **success/failure** event with probability p")
    ctx.show_optional_hint("L3_Q2", "This describes exactly one trial with two possible outcomes.")
    try_answer = ctx.answer_radio("Choose the **matching distribution**.", ["Uniform", "Bernoulli", "Exponential", "Normal"], key="L3_Q2")
    if st.button("Submit Try answer", key="L3_Q2_submit"):
        ctx.score_answer(
            pid,
            3,
            "L3_Q2",
            try_answer,
            try_answer == "Bernoulli",
            20,
            correct_answer="Bernoulli",
            explanation="Bernoulli is for one yes/no trial.",
            stage="try",
        )

    if not ctx.is_stage_complete(pid, "L3_Q2"):
        st.info("Complete Step 3 to unlock Step 4.")
        ctx.show_level_progress(pid, 3)
        ctx.show_next_button()
        return

    ctx.show_step_header(
        "Step 4 - Apply",
        "Match two new situations on your own.",
    )

    apply_questions = [
        ("L3_Q3", "**Number of defective products** in a batch of 20 separate products", ["Binomial", "Normal", "Uniform", "Exponential"], "Binomial",
         "Binomial counts successes across fixed yes/no trials."),
        ("L3_Q4", "Every value between **0 and 100** is **equally likely**", ["Poisson", "Uniform", "Exponential", "Binomial"], "Uniform",
         "Uniform gives every value in the range the same chance."),
    ]
    for cid, prompt, options, correct, explanation in apply_questions:
        ctx.show_challenge_acknowledgement(pid, cid)
        st.markdown(prompt)
        answer = ctx.answer_radio("Choose the **matching distribution**.", options, key=cid)
        if st.button("Submit Apply answer", key=f"{cid}_submit"):
            ctx.score_answer(
                pid,
                3,
                cid,
                answer,
                answer == correct,
                20,
                correct_answer=correct,
                explanation=explanation,
                stage="apply",
            )

    st.subheader("Bonus Question")
    if ctx.bonus_unlocked(pid, 3):
        st.caption("Optional. Use this to earn back missed XP.")
        st.markdown("The time between machine breakdowns is continuous and memoryless.")
        ctx.show_challenge_acknowledgement(pid, "L3_BONUS")
        ctx.show_optional_hint("L3_BONUS", "This is about the waiting time until the next event, not a count.")
        bonus_answer = ctx.answer_radio(
            "Choose the **matching distribution**.",
            ["Exponential", "Binomial", "Uniform", "Normal"],
            key="L3_BONUS",
        )
        if st.button("Submit Bonus answer", key="L3_BONUS_submit"):
            ctx.score_answer(
                pid,
                3,
                "L3_BONUS",
                bonus_answer,
                bonus_answer == "Exponential",
                20,
                correct_answer="Exponential",
                explanation="Exponential is often used for time between events.",
            )
    else:
        st.caption("Unlocks if you miss a question above.")
    ctx.show_level_progress(pid, 3)
    ctx.show_next_button()

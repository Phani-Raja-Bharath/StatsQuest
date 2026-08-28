import numpy as np
import pandas as pd
import streamlit as st


@st.cache_data(show_spinner=False)
def spread_histogram(spread):
    rng = np.random.default_rng(7)
    sample = rng.normal(50, spread, 1200)
    hist = np.histogram(sample, bins=20)
    return pd.DataFrame({"Frequency": hist[0]}, index=np.round(hist[1][:-1], 1))


def render(ctx):
    pid = ctx.pid
    completed = ctx.correct_challenges(pid)

    st.header(ctx.STORY["levels"][2])
    st.caption("Level 2 follows four steps: Watch, Explore, Try, and Apply.")

    ctx.show_step_header(
        "Step 1 - Watch",
        "Before starting this level, watch the short video. It introduces range, variance, and standard deviation.",
    )
    ctx.show_youtube_resources("level_2")
    watched = ctx.show_video_acknowledgement(pid, 2, "L2_VIDEO_ACK", key="l2_video_ack")
    if not watched:
        st.info("Complete Step 1 before starting the activity.")
        ctx.show_level_progress(pid, 2)
        ctx.show_next_button()
        return

    ctx.show_step_header(
        "Step 2 - Explore",
        ctx.content_get("level_copy.level_2_focus", "This challenge is about **range, variance, and standard deviation**."),
    )
    ctx.show_level_2_formulas()
    st.write(ctx.content_get(
        "level_copy.level_2_intro",
        "Two machines make parts near 10 units. Look at the values first, then decide which machine is more consistent.",
    ))

    machine_a = np.array([9.9, 10.0, 10.0, 10.0, 10.1])
    machine_b = np.array([6, 8, 10, 12, 14])
    ctx.show_scenario_card(
        "Machine output data",
        "Each row compares one output from Machine A and one output from Machine B. Both machines are aiming for 10 units.",
    )
    st.dataframe(pd.DataFrame({"Machine A": machine_a, "Machine B": machine_b}), hide_index=True, width="stretch")

    ctx.show_challenge_acknowledgement(pid, "L2_CONSISTENCY")
    q = ctx.answer_radio(
        ctx.content_get("level_copy.level_2_q1", "Both machines have the same **mean**. Which machine is more **consistent**?"),
        ["Machine A", "Machine B", "They are equally consistent", "There is not enough information"],
        key="l2q1",
    )
    if st.button("Submit Explore answer", key="l2submit1"):
        ctx.score_answer(
            pid,
            2,
            "L2_CONSISTENCY",
            q,
            q == "Machine A",
            30,
            correct_answer="Machine A",
            explanation=ctx.content_get("level_copy.level_2_q1_explanation", "Machine A's values stay closer to 10, so its standard deviation is smaller."),
            stage="explore",
        )
    if "L2_CONSISTENCY" in ctx.correct_challenges(pid):
        with st.expander("Show mean and standard deviation", expanded=True):
            df = pd.DataFrame({
                "Machine": ["A", "B"],
                "Mean": [machine_a.mean(), machine_b.mean()],
                "Sample SD": [machine_a.std(ddof=1), machine_b.std(ddof=1)],
            })
            st.dataframe(df, hide_index=True, width="stretch")
            st.info(ctx.content_get("level_copy.level_2_reveal", "Same mean. Different variability."))

    if not ctx.is_stage_complete(pid, "L2_CONSISTENCY"):
        st.info("Complete Step 2 to unlock Step 3.")
        ctx.show_level_progress(pid, 2)
        ctx.show_next_button()
        return

    ctx.show_step_header(
        "Step 3 - Try",
        "Predict what a larger standard deviation will do, then check with the slider.",
    )
    sd_prediction = st.radio(
        ctx.content_get("level_copy.level_2_prediction", "Before you move the slider: what do you think increasing standard deviation from 5 to 20 will do?"),
        ["Make data narrower", "Make data wider", "Move the mean", "No effect"],
        index=None,
        key="l2_sd_prediction",
    )
    sd_prediction_recorded = "L2_PREDICT_SD" in completed
    if st.button("Submit prediction", key="l2_sd_prediction_submit"):
        if not sd_prediction:
            ctx.show_challenge_status_box("one-wrong", "Prediction required", "Choose a prediction before submitting.")
        else:
            ctx.record_completion_once(pid, 2, "L2_PREDICT_SD", sd_prediction)
            sd_prediction_recorded = True
    ctx.show_record_status(
        sd_prediction_recorded,
        "Prediction submitted",
        "Prediction not submitted",
        "Your prediction is saved. Now move the standard deviation slider and compare the chart.",
        "Choose a prediction, then click Submit prediction.",
    )

    spread = st.slider(
        ctx.prominent_control_label(
            ctx.content_get("level_copy.level_2_sd_input", "Choose a standard deviation for a process")
        ),
        1,
        30,
        10,
    )
    st.caption(ctx.content_get("level_copy.level_2_sd_caption", "A larger standard deviation means values are farther from the mean."))
    st.bar_chart(spread_histogram(spread))
    st.caption(ctx.content_get("level_copy.level_2_chart_caption", "A larger standard deviation makes the chart wider."))

    ctx.show_challenge_acknowledgement(pid, "L2_SD")
    q2 = ctx.answer_radio(
        ctx.content_get("level_copy.level_2_q2", "As **standard deviation** increases, what happens to the **data values** in the chart?"),
        ["They become more spread out", "They become narrower", "The mean must increase", "The sample size becomes zero"],
        key="l2q2",
    )
    ctx.show_optional_hint("L2_SD", "Look at how far the bars move away from the mean as you move the slider.")
    if st.button("Submit Try answer", key="l2submit2"):
        if not sd_prediction_recorded:
            ctx.show_challenge_status_box("one-wrong", "Prediction required", "Submit a prediction before answering.")
        else:
            ctx.score_answer(
                pid,
                2,
                "L2_SD",
                q2,
                q2 == "They become more spread out",
                30,
                correct_answer="They become more spread out",
                explanation=ctx.content_get("level_copy.level_2_q2_explanation", "Standard deviation measures distance from the mean."),
                stage="try",
            )

    if not ctx.is_stage_complete(pid, "L2_SD"):
        st.info("Complete Step 3 to unlock Step 4.")
        ctx.show_level_progress(pid, 2)
        ctx.show_next_button()
        return

    ctx.show_step_header(
        "Step 4 - Apply",
        "Use the same idea in a new situation.",
    )
    st.write(
        "Two delivery processes both average the same output. A quality report gives you their "
        "standard deviations and asks you to recommend one."
    )
    ctx.show_challenge_acknowledgement(pid, "L2_APPLY")
    q3 = ctx.answer_radio(
        "Apply question: two processes have the same average output. Process A has SD = 1.2 and Process B has SD = 5.8. "
        "Which process is more consistent?",
        ["Process A", "Process B", "They are equally consistent", "There is not enough information"],
        key="l2apply",
    )
    if st.button("Submit Apply answer", key="l2submit_apply"):
        ctx.score_answer(
            pid,
            2,
            "L2_APPLY",
            q3,
            q3 == "Process A",
            30,
            correct_answer="Process A",
            explanation="A smaller standard deviation means the process's outputs stay closer to the average, run after run.",
            stage="apply",
        )

    st.subheader("Bonus Question")
    if ctx.bonus_unlocked(pid, 2):
        st.caption("Optional. Use this to earn back missed XP.")
        ctx.show_challenge_acknowledgement(pid, "L2_BONUS")
        q4 = ctx.answer_radio(
            ctx.content_get("level_copy.level_2_bonus_q", "Which quantity is the square of the **standard deviation**?"),
            ["Variance", "Mean", "Median", "Range"],
            key="l2q3",
        )
        if st.button("Submit Bonus answer", key="l2submit3"):
            ctx.score_answer(
                pid,
                2,
                "L2_BONUS",
                q4,
                q4 == "Variance",
                30,
                correct_answer="Variance",
                explanation=ctx.content_get("level_copy.level_2_bonus_explanation", "Variance is standard deviation squared."),
            )
    else:
        st.caption("Unlocks if you miss a question above.")
    ctx.show_level_progress(pid, 2)
    ctx.show_next_button()

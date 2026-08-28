import numpy as np
import streamlit as st


def render(ctx):
    pid = ctx.pid
    completed = ctx.correct_challenges(pid)

    st.header(ctx.STORY["levels"][1])
    st.caption("Level 1 follows four steps: Watch, Explore, Try, and Apply.")

    ctx.show_step_header(
        "Step 1 - Watch",
        "Before starting this level, watch the short video. It introduces mean, median, mode, and outliers.",
    )
    ctx.show_youtube_resources("level_1")
    watched = ctx.show_video_acknowledgement(pid, 1, "L1_VIDEO_ACK", key="l1_video_ack")
    if not watched:
        st.info("Complete Step 1 before starting the activity.")
        ctx.show_level_progress(pid, 1)
        ctx.show_next_button()
        return

    ctx.show_step_header(
        "Step 2 - Explore",
        "Change one value in the commute data and compare the statistics before answering.",
    )
    st.markdown("#### Formula reference")
    ctx.show_level_1_formulas()

    st.divider()
    st.markdown("#### Commute-time activity")
    data = [15, 18, 20, 22, 25, 30, 35]
    ctx.show_scenario_card(
        "Original commute data",
        "These are seven student commute times, measured in minutes, before any unusual value is added.",
        data,
    )
    ctx.show_descriptive_stats(data)

    prediction = st.radio(
        "Prediction: if the final commute becomes very large, which statistic do you think will change the most?",
        ["Mean changes most", "Median changes most", "Mode changes most", "They change equally"],
        index=None,
        key="l1_prediction",
    )
    prediction_recorded = "L1_PREDICT" in completed
    if st.button("Submit prediction", key="l1_prediction_submit"):
        if not prediction:
            ctx.show_challenge_status_box("one-wrong", "Prediction required", "Choose a prediction before submitting.")
        else:
            ctx.record_completion_once(pid, 1, "L1_PREDICT", prediction)
            prediction_recorded = True
    ctx.show_record_status(
        prediction_recorded,
        "Prediction submitted",
        "Prediction not submitted",
        "Your prediction is saved. Now change the commute time and compare the statistics.",
        "Choose a prediction, then click Submit prediction.",
    )

    ctx.show_challenge_acknowledgement(pid, "L1_OUTLIER")
    outlier = st.number_input(
        ctx.prominent_control_label("Replace 35 minutes with an unusually large commute time:"),
        min_value=60,
        max_value=600,
        value=600,
        step=10,
        key="l1_outlier_value",
    )
    changed = [15, 18, 20, 22, 25, 30, outlier]
    ctx.show_scenario_card(
        "Commute data after one change",
        "The final commute time has been replaced with the unusually large value you entered.",
        changed,
    )
    ctx.show_descriptive_stats(changed, label_prefix="New ")

    observed = st.radio(
        "Observation: did the result match your prediction?",
        ["Yes", "No", "I am not sure"],
        index=None,
        key="l1_observe",
    )
    observation_recorded = "L1_OBSERVE" in completed
    if st.button("Submit observation", key="l1_observation_submit"):
        if not observed:
            ctx.show_challenge_status_box("one-wrong", "Observation required", "Choose an observation before submitting.")
        else:
            ctx.record_completion_once(pid, 1, "L1_OBSERVE", observed)
            observation_recorded = True
    ctx.show_record_status(
        observation_recorded,
        "Observation submitted",
        "Observation not submitted",
        "Your observation is saved. You can now answer the Explore question.",
        "Choose whether the result matched your prediction, then click Submit observation.",
    )

    q1 = ctx.answer_radio(
        "Explore question: which statistic changes the most because of the **very large outlier**?",
        ["Mean", "Median", "Mode", "They all change equally"],
        key="l1q1",
    )
    if st.button("Submit Explore answer", key="l1submit1"):
        if not prediction_recorded or not observation_recorded:
            ctx.show_challenge_status_box(
                "one-wrong",
                "Required steps missing",
                "Submit a prediction and submit your observation before answering.",
            )
        else:
            ctx.score_answer(
                pid,
                1,
                "L1_OUTLIER",
                q1,
                q1 == "Mean",
                25,
                correct_answer="Mean",
                explanation="The mean uses every value, so one very large value pulls it up.",
                stage="explore",
            )

    if not ctx.is_stage_complete(pid, "L1_OUTLIER"):
        st.info("Complete Step 2 to unlock Step 3.")
        ctx.show_level_progress(pid, 1)
        ctx.show_next_button()
        return

    ctx.show_step_header(
        "Step 3 - Try",
        "Now solve a similar problem.",
    )
    ctx.show_challenge_acknowledgement(pid, "L1_CENTER")
    hospital_base_waits = [8, 10, 11, 12, 13, 14]
    hospital_waits = hospital_base_waits + [90]
    ctx.show_scenario_card(
        "Hospital wait data",
        "Six patients waited close to the same amount of time. One patient waited much longer.",
        hospital_waits,
    )
    with st.expander("Need a hint?"):
        st.write("Look for the statistic that stays close to most of the wait times.")

    q2 = ctx.answer_radio(
        "Try question: one patient waited much longer than the others. Which statistic should the hospital report?",
        ["Mean", "Median", "Mode", "Range"],
        key="l1q2",
    )
    if st.button("Submit Try answer", key="l1submit2"):
        ctx.score_answer(
            pid,
            1,
            "L1_CENTER",
            q2,
            q2 == "Median",
            25,
            correct_answer="Median",
            explanation="The median stays close to the usual waits because one unusually long wait does not pull it much.",
            stage="try",
        )

    if ctx.is_stage_complete(pid, "L1_CENTER"):
        with st.expander("Show hospital statistics", expanded=False):
            before_col, after_col = st.columns(2)
            with before_col:
                st.markdown("**Usual waits only**")
                st.metric("Mean", f"{np.mean(hospital_base_waits):.1f}")
                st.metric("Median", f"{np.median(hospital_base_waits):.1f}")
            with after_col:
                st.markdown("**With unusually long wait**")
                st.metric("Mean", f"{np.mean(hospital_waits):.1f}")
                st.metric("Median", f"{np.median(hospital_waits):.1f}")

    if not ctx.is_stage_complete(pid, "L1_CENTER"):
        st.info("Complete Step 3 to unlock Step 4.")
        ctx.show_level_progress(pid, 1)
        ctx.show_next_button()
        return

    ctx.show_step_header(
        "Step 4 - Apply",
        "Use the same idea in a new situation.",
    )
    salaries = [42, 45, 47, 48, 51, 55, 600]
    st.write(
        "A small company is describing salaries to a new applicant. Most employees are staff members, "
        "and one value belongs to a very highly paid executive."
    )
    ctx.show_scenario_card(
        "Employee salary data",
        "These salaries are shown in thousands of dollars.",
        salaries,
    )
    ctx.show_challenge_acknowledgement(pid, "L1_APPLY")
    q3 = ctx.answer_radio(
        "Apply question: the company wants one salary statistic for the staff salaries. Which statistic should the company report?",
        ["Mean", "Median", "Mode", "Range"],
        key="l1apply",
    )
    if st.button("Submit Apply answer", key="l1submit_apply"):
        ctx.score_answer(
            pid,
            1,
            "L1_APPLY",
            q3,
            q3 == "Median",
            25,
            correct_answer="Median",
            explanation="Most staff salaries are near 42 to 55 thousand dollars, while 600 thousand is unusually large. The median is less affected by the unusually large value.",
            stage="apply",
        )

    if not ctx.is_stage_complete(pid, "L1_APPLY"):
        st.info("Complete Step 4 to finish the required Level 1 questions.")
        ctx.show_level_progress(pid, 1)
        ctx.show_next_button()
        return

    ctx.show_step_header("Step 5 - Complete")
    ctx.show_challenge_acknowledgement(pid, "L1_REFLECT")
    reflection = st.radio(
        "Finish this thought: when data has an extreme outlier, I should compare ______ before choosing a statistic.",
        ["mean and median", "only the largest value", "only the sample size", "only the mode"],
        index=None,
        key="l1_reflection",
    )
    if st.button("Submit Complete answer", key="l1_reflection_submit"):
        ctx.score_answer(
            pid,
            1,
            "L1_REFLECT",
            reflection,
            reflection == "mean and median",
            0,
            correct_answer="mean and median",
            explanation="Mean and median can tell different stories when one value is unusually large.",
        )

    st.subheader("Bonus Question")
    if ctx.bonus_unlocked(pid, 1):
        st.caption("Optional. Use this to earn back missed XP.")
        ctx.show_challenge_acknowledgement(pid, "L1_BONUS")
        bonus = ctx.answer_radio(
            "If one value becomes a **very large outlier** and the smallest value stays the same, what happens to the **range**?",
            ["The range increases", "The range decreases", "The range stays the same", "The range becomes the median"],
            key="l1q3",
        )
        if st.button("Submit Bonus answer", key="l1submit3"):
            ctx.score_answer(
                pid,
                1,
                "L1_BONUS",
                bonus,
                bonus == "The range increases",
                25,
                correct_answer="The range increases",
                explanation="Range is maximum minus minimum. If the maximum gets larger and the minimum stays the same, the range increases.",
            )
    else:
        st.caption("Unlocks if you miss a question above.")

    ctx.show_level_progress(pid, 1)
    ctx.show_next_button()

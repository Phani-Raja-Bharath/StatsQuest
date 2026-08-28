import math

import numpy as np
import pandas as pd
import streamlit as st


@st.cache_data(show_spinner=False)
def monte_carlo_workloads(arrivals, service, runs):
    rng = np.random.default_rng(42)
    counts = rng.poisson(arrivals, runs)
    workloads = np.zeros(runs)
    nonzero = counts > 0
    workloads[nonzero] = rng.gamma(shape=counts[nonzero], scale=service)
    return workloads


def render(ctx):
    pid = ctx.pid
    completed = ctx.correct_challenges(pid)

    st.header(ctx.STORY["levels"][5])
    st.caption("Level 5 follows four steps: Watch, Explore, Try, and Apply.")

    ctx.show_step_header(
        "Step 1 - Watch",
        "Before starting this level, watch the short video. It introduces the Monte Carlo idea.",
    )
    ctx.show_youtube_resources("level_5")
    watched = ctx.show_video_acknowledgement(pid, 5, "L5_VIDEO_ACK", key="l5_video_ack")
    if not watched:
        st.info("Complete Step 1 before starting the activity.")
        ctx.show_level_progress(pid, 5)
        ctx.show_next_button()
        return

    ctx.show_step_header(
        "Step 2 - Explore",
        "Airport security workload depends on how many passengers arrive and how long each one takes.",
    )
    st.info("A fixed model gives one answer. A random simulation gives many possible answers, so you can see risk.")

    prediction = st.radio(
        ctx.content_get(
            "level_copy.level_5_prediction",
            "Before you try it: as the number of simulation runs grows, what do you think happens to the shape of the results?",
        ),
        ["It gets steadier and more stable", "It gets more random each time", "It stays exactly the same shape no matter what", "It stops being useful"],
        index=None,
        key="l5_prediction",
    )
    prediction_recorded = "L5_PREDICT" in completed
    if st.button("Submit prediction", key="l5_prediction_submit"):
        if not prediction:
            ctx.show_challenge_status_box("one-wrong", "Prediction required", "Choose a prediction before submitting.")
        else:
            ctx.record_completion_once(pid, 5, "L5_PREDICT", prediction)
            prediction_recorded = True
    ctx.show_record_status(
        prediction_recorded,
        "Prediction submitted",
        "Prediction not submitted",
        "Your prediction is saved. Now change the number of runs and compare the results.",
        "Choose a prediction, then click Submit prediction.",
    )

    arrivals = st.slider("Average arrivals / 10 min", 2, 20, 8)
    service = st.slider("Average service time (min)", 0.5, 4.0, 1.5, 0.1)
    runs = st.selectbox("Monte Carlo runs", options=[10, 100, 1000, 10000], index=2)
    st.caption("More runs make results steadier, but uncertainty is still there.")

    workloads = monte_carlo_workloads(arrivals, service, runs)

    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Estimated mean", f"{workloads.mean():.2f}")
    col_b.metric("Std. deviation", f"{workloads.std(ddof=1):.2f}" if runs > 1 else "-")
    col_c.metric("95th percentile", f"{np.percentile(workloads, 95):.2f}")
    st.caption("95th percentile: about 95% of runs are at or below this value.")

    hist = np.histogram(workloads, bins=min(30, max(5, int(math.sqrt(runs)))))
    st.bar_chart(pd.DataFrame({"Frequency": hist[0]}, index=np.round(hist[1][:-1], 1)))
    st.caption("This chart shows the possible workload totals from many runs.")

    observed = st.radio(
        ctx.content_get("level_copy.level_5_observe", "Did that match what you expected? Try changing the number of runs above to compare."),
        ["Yes", "No", "I am not sure"],
        index=None,
        key="l5_observe",
    )
    observation_recorded = "L5_OBSERVE" in completed
    if st.button("Submit observation", key="l5_observation_submit"):
        if not observed:
            ctx.show_challenge_status_box("one-wrong", "Observation required", "Choose an observation before submitting.")
        else:
            ctx.record_completion_once(pid, 5, "L5_OBSERVE", observed)
            observation_recorded = True
    ctx.show_record_status(
        observation_recorded,
        "Observation submitted",
        "Observation not submitted",
        "Your observation is saved. You can now answer the Explore question.",
        "Choose whether the result matched your prediction, then click Submit observation.",
    )

    ctx.show_challenge_acknowledgement(pid, "L5_STABILITY")
    q1 = ctx.answer_radio(
        "Explore question: what usually happens to a **Monte Carlo estimate** as the **number of runs** increases?",
        [
            "It generally becomes more stable",
            "It always becomes larger",
            "It becomes fixed after 100 runs",
            "It removes the need to model variation",
        ],
        key="l5q1",
    )
    if st.button("Submit Explore answer", key="l5submit1"):
        if not prediction_recorded or not observation_recorded:
            ctx.show_challenge_status_box(
                "one-wrong",
                "Required steps missing",
                "Submit a prediction and submit your observation before answering.",
            )
        else:
            ctx.score_answer(
                pid,
                5,
                "L5_STABILITY",
                q1,
                q1 == "It generally becomes more stable",
                45,
                correct_answer="It generally becomes more stable",
                explanation="More runs average out random noise.",
                stage="explore",
            )

    if not ctx.is_stage_complete(pid, "L5_STABILITY"):
        st.info("Complete Step 2 to unlock Step 3.")
        ctx.show_level_progress(pid, 5)
        ctx.show_next_button()
        return

    ctx.show_step_header(
        "Step 3 - Try",
        "Now explain why Monte Carlo is run many times.",
    )
    ctx.show_challenge_acknowledgement(pid, "L5_PURPOSE")
    q2 = ctx.answer_radio(
        "Try question: why run **Monte Carlo** many times instead of using **one random simulation**?",
        [
            "To estimate possible outcomes and their chances",
            "To eliminate all uncertainty",
            "To guarantee the maximum possible result",
            "To make every run identical",
        ],
        key="l5q2",
    )
    ctx.show_optional_hint("L5_PURPOSE", "Think about how much randomness there is from one single run to the next.")
    if st.button("Submit Try answer", key="l5submit2"):
        ctx.score_answer(
            pid,
            5,
            "L5_PURPOSE",
            q2,
            q2 == "To estimate possible outcomes and their chances",
            45,
            correct_answer="To estimate possible outcomes and their chances",
            explanation="Monte Carlo repeats random simulations to show what could happen.",
            stage="try",
        )

    if not ctx.is_stage_complete(pid, "L5_PURPOSE"):
        st.info("Complete Step 3 to unlock Step 4.")
        ctx.show_level_progress(pid, 5)
        ctx.show_next_button()
        return

    ctx.show_step_header(
        "Step 4 - Apply",
        "Use the same idea to make a decision in a new situation.",
    )
    st.write(
        "A project manager wants to estimate the probability that a construction project finishes "
        "within 90 days."
    )
    ctx.show_challenge_acknowledgement(pid, "L5_APPLY")
    q3 = ctx.answer_radio(
        "Apply question: why should the project manager run the simulation many times instead of once?",
        [
            "To estimate possible outcomes and their chances",
            "To guarantee the project finishes on time",
            "To remove randomness from the estimate",
            "To make every simulated project identical",
        ],
        key="l5apply",
    )
    if st.button("Submit Apply answer", key="l5submit_apply"):
        ctx.score_answer(
            pid,
            5,
            "L5_APPLY",
            q3,
            q3 == "To estimate possible outcomes and their chances",
            45,
            correct_answer="To estimate possible outcomes and their chances",
            explanation="One run only shows one possible outcome; many runs show the range of outcomes and how likely each is.",
            stage="apply",
        )

    st.subheader("Bonus Question")
    if ctx.bonus_unlocked(pid, 5):
        st.caption("Optional. Use this to earn back missed XP.")
        ctx.show_challenge_acknowledgement(pid, "L5_BONUS")
        q4 = ctx.answer_radio(
            "Which method can make a **Monte Carlo estimate** more **precise**?",
            [
                "A method to get more precise estimates with fewer runs",
                "A method that guarantees zero error",
                "A method that removes the need for randomness",
                "A method that always chooses the largest outcome",
            ],
            key="l5q3",
        )
        if st.button("Submit Bonus answer", key="l5submit3"):
            ctx.score_answer(
                pid,
                5,
                "L5_BONUS",
                q4,
                q4 == "A method to get more precise estimates with fewer runs",
                45,
                correct_answer="A method to get more precise estimates with fewer runs",
                explanation="Variance reduction lowers simulation noise.",
            )
    else:
        st.caption("Unlocks if you miss a question above.")

    ctx.show_boss_progress(ctx.xp)
    if ctx.xp >= ctx.PERFECT_SCORE:
        st.markdown(ctx.STORY["epilogue"])
    ctx.show_level_progress(pid, 5)
    ctx.show_next_button()

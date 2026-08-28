import numpy as np
import pandas as pd
import streamlit as st


@st.cache_data(show_spinner=False)
def arrival_count_histogram(rate):
    rng = np.random.default_rng(11)
    counts = rng.poisson(rate, 1000)
    values, freq = np.unique(counts, return_counts=True)
    return pd.DataFrame({"Frequency": freq}, index=values)


def render(ctx):
    pid = ctx.pid
    completed = ctx.correct_challenges(pid)

    st.header(ctx.STORY["levels"][4])
    st.caption("Level 4 follows four steps: Watch, Explore, Try, and Apply.")

    ctx.show_step_header(
        "Step 1 - Watch",
        "Before starting this level, watch the short video. It shows why random inputs make arrival "
        "simulations realistic.",
    )
    ctx.show_youtube_resources("level_4")
    watched = ctx.show_video_acknowledgement(pid, 4, "L4_VIDEO_ACK", key="l4_video_ack")
    if not watched:
        st.info("Complete Step 1 before starting the activity.")
        ctx.show_level_progress(pid, 4)
        ctx.show_next_button()
        return

    ctx.show_step_header(
        "Step 2 - Explore",
        "An airport wants to model passengers arriving at security. Use Poisson for the number of arrivals "
        "and Exponential for the time between arrivals.",
    )
    ctx.show_level_4_formulas()

    prediction = st.radio(
        ctx.content_get(
            "level_copy.level_4_prediction",
            "Before you try it: if the average arrival rate doubles, what do you think happens to the average wait between passengers?",
        ),
        ["It gets longer", "It gets shorter", "It stays the same", "There's no relationship"],
        index=None,
        key="l4_prediction",
    )
    prediction_recorded = "L4_PREDICT" in completed
    if st.button("Submit prediction", key="l4_prediction_submit"):
        if not prediction:
            ctx.show_challenge_status_box("one-wrong", "Prediction required", "Choose a prediction before submitting.")
        else:
            ctx.record_completion_once(pid, 4, "L4_PREDICT", prediction)
            prediction_recorded = True
    ctx.show_record_status(
        prediction_recorded,
        "Prediction submitted",
        "Prediction not submitted",
        "Your prediction is saved. Now change the arrival rate and compare the wait time.",
        "Choose a prediction, then click Submit prediction.",
    )

    rate = st.slider(
        ctx.prominent_control_label("Average passengers arriving per 10 minutes"),
        1,
        20,
        5,
    )
    mean_wait = 10 / rate
    st.metric("Estimated average wait time", f"{mean_wait:.2f} min")
    st.caption("Mean wait time = time interval / arrival rate. More arrivals means shorter waits.")
    st.bar_chart(arrival_count_histogram(rate))
    st.caption("This chart shows passenger counts in 10-minute blocks.")

    observed = st.radio(
        ctx.content_get("level_copy.level_4_observe", "Did that match what you expected?"),
        ["Yes", "No", "I am not sure"],
        index=None,
        key="l4_observe",
    )
    observation_recorded = "L4_OBSERVE" in completed
    if st.button("Submit observation", key="l4_observation_submit"):
        if not observed:
            ctx.show_challenge_status_box("one-wrong", "Observation required", "Choose an observation before submitting.")
        else:
            ctx.record_completion_once(pid, 4, "L4_OBSERVE", observed)
            observation_recorded = True
    ctx.show_record_status(
        observation_recorded,
        "Observation submitted",
        "Observation not submitted",
        "Your observation is saved. You can now answer the Explore question.",
        "Choose whether the result matched your prediction, then click Submit observation.",
    )

    ctx.show_challenge_acknowledgement(pid, "L4_POISSON")
    q1 = ctx.answer_radio(
        "Explore question: which distribution models the **number of passengers** arriving in a **fixed time**?",
        ["Poisson", "Exponential", "Normal", "Bernoulli"],
        key="l4q1",
    )
    if st.button("Submit Explore answer", key="l4submit1"):
        if not prediction_recorded or not observation_recorded:
            ctx.show_challenge_status_box(
                "one-wrong",
                "Required steps missing",
                "Submit a prediction and submit your observation before answering.",
            )
        else:
            ctx.score_answer(
                pid,
                4,
                "L4_POISSON",
                q1,
                q1 == "Poisson",
                35,
                correct_answer="Poisson",
                explanation="Poisson models how many events happen in a fixed time.",
                stage="explore",
            )

    if not ctx.is_stage_complete(pid, "L4_POISSON"):
        st.info("Complete Step 2 to unlock Step 3.")
        ctx.show_level_progress(pid, 4)
        ctx.show_next_button()
        return

    ctx.show_step_header(
        "Step 3 - Try",
        "Now identify the distribution for the time between arrivals.",
    )
    ctx.show_challenge_acknowledgement(pid, "L4_EXP")
    q2 = ctx.answer_radio(
        "Try question: which distribution models the **time until the next passenger** arrives?",
        ["Binomial", "Exponential", "Uniform", "Poisson"],
        key="l4q2",
    )
    ctx.show_optional_hint("L4_EXP", "You are measuring the gap in time before one single passenger shows up next.")
    if st.button("Submit Try answer", key="l4submit2"):
        ctx.score_answer(
            pid,
            4,
            "L4_EXP",
            q2,
            q2 == "Exponential",
            35,
            correct_answer="Exponential",
            explanation="Exponential models the wait until the next event.",
            stage="try",
        )

    if not ctx.is_stage_complete(pid, "L4_EXP"):
        st.info("Complete Step 3 to unlock Step 4.")
        ctx.show_level_progress(pid, 4)
        ctx.show_next_button()
        return

    ctx.show_step_header(
        "Step 4 - Apply",
        "Use the same idea in a new situation.",
    )
    st.write(
        "A help desk is building a simulation of its call queue. It needs to model the time between "
        "the moment one call ends and the moment the next call starts."
    )
    ctx.show_challenge_acknowledgement(pid, "L4_APPLY")
    q3 = ctx.answer_radio(
        "Apply question: which distribution should the simulation use for the **time between successive calls**?",
        ["Poisson", "Exponential", "Normal", "Binomial"],
        key="l4apply",
    )
    if st.button("Submit Apply answer", key="l4submit_apply"):
        ctx.score_answer(
            pid,
            4,
            "L4_APPLY",
            q3,
            q3 == "Exponential",
            35,
            correct_answer="Exponential",
            explanation="This is still a waiting time between events, just in a new setting -- Exponential applies here too.",
            stage="apply",
        )

    st.subheader("Bonus Question")
    if ctx.bonus_unlocked(pid, 4):
        st.caption("Optional. Use this to earn back missed XP.")
        ctx.show_challenge_acknowledgement(pid, "L4_BONUS")
        q4 = ctx.answer_radio(
            "If the **average arrival rate doubles**, what happens to the **average wait time**?",
            ["It is halved", "It doubles", "It stays the same", "It becomes negative"],
            key="l4q3",
        )
        if st.button("Submit Bonus answer", key="l4submit3"):
            ctx.score_answer(
                pid,
                4,
                "L4_BONUS",
                q4,
                q4 == "It is halved",
                35,
                correct_answer="It is halved",
                explanation="When arrivals happen twice as often, the average wait is cut in half.",
            )
    else:
        st.caption("Unlocks if you miss a question above.")
    ctx.show_level_progress(pid, 4)
    ctx.show_next_button()

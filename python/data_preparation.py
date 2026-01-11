import pandas as pd
from sklearn.preprocessing import MinMaxScaler
from sklearn.model_selection import train_test_split
from imblearn.over_sampling import SMOTE
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, f1_score, confusion_matrix, accuracy_score
import numpy as np
import os

# --- Configuration ---
FILE_NAME = 'course_acceptance_probability_raw_data.xlsx'
TARGET_COLUMN = "If accepted, will you immediately confirm your slot in this course?"
SEED = 42 # For reproducible splits and SMOTE
# Model will be trained on data where 'Yes' (Confirm) = 0 and 'No' (Decline) = 1

def prepare_data(file_path):
    """
    Loads the data, performs feature selection, encoding, imputation, normalization,
    and returns the training and testing sets, separated by features (X) and label (y).
    """
    try:
        # Load the Excel file 
        df = pd.read_excel(file_path)
    except FileNotFoundError:
        print(f"Error: File not found at {file_path}. Please ensure the file is in the correct directory.")
        return None, None, None, None

    # 1. Feature Selection
    ohe_features = ['SHS Strand/Track: ', 'Type of High School graduated from: ']
    scale_features = ['General Weighted Average (GWA): ']
    
    # Identify all binary (Yes/No) columns including the target label.
    binary_features = [col for col in df.columns if col not in ['Timestamp', 'Intended program/course: '] + ohe_features + scale_features]
    
    # Create the initial feature list (X) and the target list (y)
    X_features = ohe_features + scale_features + [col for col in binary_features if col != TARGET_COLUMN]
    y_target = TARGET_COLUMN

    df_selected = df[X_features + [y_target]].copy()
    initial_rows = len(df_selected)

    # 2. Binary Encoding (Yes=0, No=1)
    encoding_map = {'Yes': 0, 'No': 1}

    for col in binary_features:
        if col in df_selected.columns:
            # We map 'Yes' to 0 and 'No' to 1 for consistency.
            df_selected[col] = df_selected[col].map(encoding_map)
            
    # 3. Separation of Features (X) and Target (y)
    X = df_selected.drop(columns=[y_target])
    y = df_selected[y_target]
    
    # 4. Imputation and Cleaning
    
    # A. Clean Target (y): Drop rows where the target label is missing.
    valid_indices = y.dropna().index
    X = X.loc[valid_indices]
    y = y.loc[valid_indices]
    
    # B. Impute Features (X)
    
    # B1. Impute Binary Features (using mode: 0=Yes or 1=No)
    for col in [c for c in binary_features if c != TARGET_COLUMN]:
        if not X[col].empty:
            mode_value = X[col].mode().iloc[0] if not X[col].mode().empty else 0
            # Note: Using .loc ensures we modify the original DataFrame slice
            X.loc[:, col].fillna(mode_value, inplace=True)

    # B2. Impute GWA (Numerical Feature) using the mean
    if not X[scale_features].empty:
        gwa_mean = X[scale_features].mean().iloc[0]
        # Note: Using .loc ensures we modify the original DataFrame slice
        X.loc[:, scale_features].fillna(gwa_mean, inplace=True)
    
    # B3. Impute Categorical Features (using 'Missing' string) before OHE
    for col in ohe_features:
        # Note: Using .loc ensures we modify the original DataFrame slice
        X.loc[:, col].fillna('Missing', inplace=True)


    # 5. One-Hot Encoding (OHE) for nominal features
    X = pd.get_dummies(X, columns=ohe_features, drop_first=True)

    # 6. Data Splitting (e.g., 80% Train, 20% Test)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=SEED, stratify=y
    )

    # 7. Normalization (Min-Max Scaling)
    scaler = MinMaxScaler()
    scale_cols_in_X = [col for col in X_train.columns if any(s in col for s in scale_features)]
    
    if scale_cols_in_X:
        # Suppress SettingWithCopyWarning by using .loc
        X_train.loc[:, scale_cols_in_X] = scaler.fit_transform(X_train[scale_cols_in_X])
        X_test.loc[:, scale_cols_in_X] = scaler.transform(X_test[scale_cols_in_X])
    
    # 8. SMOTE for Imbalance (Applied to Training Data ONLY)
    smote = SMOTE(random_state=SEED)
    X_train_resampled, y_train_resampled = smote.fit_resample(X_train, y_train)

    return X_train_resampled, X_test, y_train_resampled, y_test

def train_and_evaluate_model(model_name, model_instance, X_train, X_test, y_train, y_test):
    """Trains and evaluates a given model instance."""
    print(f"\n--- Model Training ({model_name}) ---")
    
    # Train the model
    model_instance.fit(X_train, y_train)
    print(f"{model_name} training complete.")
    
    # Prediction on the unseen test set
    y_pred = model_instance.predict(X_test)
    
    # Evaluation
    print(f"\n--- Model Evaluation ({model_name} on Unseen Test Data) ---")
    
    target_names = ['0 (Yes/Confirm)', '1 (No/Decline)']
    
    # Print the comprehensive classification report
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, target_names=target_names))

    # Print overall metrics
    accuracy = accuracy_score(y_test, y_pred)
    f1_score_macro = f1_score(y_test, y_pred, average='macro')
    
    print(f"\nOverall Accuracy (Total Correct Predictions): {accuracy:.4f}")
    print(f"Macro F1-Score (Balanced performance across both classes): {f1_score_macro:.4f}")
    
    return model_instance, accuracy, f1_score_macro

def get_logistic_regression_insights(model, feature_names):
    """
    Analyzes and prints the feature coefficients from the Logistic Regression model.
    """
    print("\n--- Feature Importance Analysis (Logistic Regression Coefficients) ---")
    
    # Get the coefficients and feature names
    coefficients = model.coef_[0]
    feature_importance = pd.Series(coefficients, index=feature_names)
    
    # Sort by absolute value to find most impactful features
    top_5_pos = feature_importance.sort_values(ascending=False).head(5)
    top_5_neg = feature_importance.sort_values(ascending=True).head(5)
    
    # Print Positive Predictors (Pushing toward Class 1: No/Decline)
    print("\nTop 5 POSITIVE Predictors (Higher value increases 'No/Decline' probability - Class 1):")
    print("(e.g., higher GWA score or a 'No' answer to a key question)")
    print(top_5_pos)
    
    # Print Negative Predictors (Pushing toward Class 0: Yes/Confirm)
    print("\nTop 5 NEGATIVE Predictors (Lower value increases 'Yes/Confirm' probability - Class 0):")
    print("(e.g., lower GWA score or a 'Yes' answer to a key question)")
    print(top_5_neg)
    
    # Return the series for external use
    return feature_importance

# --- Execution Block ---
if __name__ == '__main__':
    print(f"Loading data from: {FILE_NAME}")

    # Prepare data (Imputation, Encoding, Splitting, SMOTE)
    X_train, X_test, y_train, y_test = prepare_data(FILE_NAME) # [Image of data preprocessing steps]

    if X_train is not None:
        
        # 1. TRAIN AND EVALUATE LOGISTIC REGRESSION (Baseline)
        lr_model, lr_accuracy, lr_f1 = train_and_evaluate_model(
            "Logistic Regression",
            LogisticRegression(random_state=SEED, solver='liblinear', max_iter=200),
            X_train, X_test, y_train, y_test
        )
        
        # 2. FEATURE IMPORTANCE ANALYSIS
        # This is the key insight generation step for the paper
        feature_coefficients = get_logistic_regression_insights(lr_model, X_train.columns)

        # 3. TRAIN AND EVALUATE RANDOM FOREST (Comparison Model)
        rf_model, rf_accuracy, rf_f1 = train_and_evaluate_model(
            "Random Forest Classifier",
            RandomForestClassifier(random_state=SEED, n_estimators=100),
            X_train, X_test, y_train, y_test
        )
        
        print("\n--- Summary of Model Performance ---")
        print(f"Logistic Regression Macro F1-Score: {lr_f1:.4f}")
        print(f"Random Forest Macro F1-Score: {rf_f1:.4f}")